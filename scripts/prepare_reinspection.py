"""Archive local inspection evidence, then reset inspections for a new test run."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.models.database import Inspection, Order, audit, connect_database


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def main() -> None:
    settings = Settings.from_env()
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("This local reset supports SQLite only")
    db_path = Path(settings.database_url.removeprefix("sqlite:///"))
    db_path = db_path.resolve()
    if not db_path.is_file() or settings.data_dir.resolve() not in db_path.parents:
        raise RuntimeError("Configured database must exist within the local data directory")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = settings.data_dir / "inspection_reset" / stamp
    if archive.exists():
        raise RuntimeError("Archive directory already exists; retry after the next UTC second")
    archive.mkdir(parents=True)

    engine, sessions = connect_database(settings.database_url)
    try:
        with sessions() as db:
            orders = {order.id: order for order in db.scalars(select(Order)).all()}
            inspections = db.scalars(select(Inspection).order_by(Inspection.created_at, Inspection.id)).all()
            entries = []
            for inspection in inspections:
                source = Path(inspection.image_path).resolve()
                if source.parent != (settings.data_dir / "uploads").resolve() or not source.is_file():
                    raise RuntimeError(f"Missing or external inspection image: {inspection.id}")
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if digest != inspection.image_sha256:
                    raise RuntimeError(f"Inspection image hash mismatch: {inspection.id}")
                order = orders[inspection.order_id]
                group = "verified" if inspection.status == "VERIFIED" else "review"
                name = f"{safe_name(order.reference)}__{inspection.id}__{inspection.photo_id}{source.suffix.lower()}"
                destination = archive / group / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise RuntimeError(f"Archive copy failed verification: {inspection.id}")
                entries.append({"order_reference": order.reference, "order_id": order.id,
                                "inspection_id": inspection.id, "photo_id": inspection.photo_id,
                                "inspection_status": inspection.status, "image_sha256": digest,
                                "original_path": str(source), "archive_path": str(destination.relative_to(archive))})
            index = {"created_at_utc": stamp, "source_database": str(db_path),
                     "orders": [{"reference": order.reference, "id": order.id,
                                 "items": {item.product.sku: item.quantity for item in order.items}}
                                for order in sorted(orders.values(), key=lambda row: row.reference)],
                     "images": entries}
            (archive / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

        backup_path = archive / "proofsight.before-reset.db"
        with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as target:
            source.backup(target)
        with sqlite3.connect(backup_path) as backup:
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Database backup failed integrity check")
            if backup.execute("SELECT count(*) FROM inspections").fetchone()[0] != len(entries):
                raise RuntimeError("Database backup inspection count differs from image archive")
        if sum(1 for item in entries if (archive / item["archive_path"]).is_file()) != len(entries):
            raise RuntimeError("Image archive is incomplete")

        # Preserve registration, catalog, manifest, inventory, and immutable audit history.
        # All inspection-dependent operational state is removed in FK-safe order.
        with engine.begin() as connection:
            for table in ("task_transitions", "picking_tasks", "removal_tasks", "approvals",
                          "operational_tasks", "corrective_actions", "discrepancies",
                          "inspection_observations", "inspections"):
                connection.execute(text(f"DELETE FROM {table}"))
            connection.execute(text("""UPDATE orders SET status='PENDING_INSPECTION',
                preparation_status='READY_FOR_INSPECTION', shipping_status='NOT_READY',
                requires_reinspection=0, latest_inspection_id=NULL, version=1"""))
        with sessions() as db:
            audit(db, "LOCAL_INSPECTIONS_RESET", "all-orders",
                  {"archive": str(archive), "inspection_count": len(entries),
                   "verified_images": sum(item["inspection_status"] == "VERIFIED" for item in entries),
                   "review_images": sum(item["inspection_status"] != "VERIFIED" for item in entries)})
            db.commit()
        print(json.dumps({"archive": str(archive), "orders": len(orders),
                          "verified_images": sum(item["inspection_status"] == "VERIFIED" for item in entries),
                          "review_images": sum(item["inspection_status"] != "VERIFIED" for item in entries),
                          "inspections_reset": len(entries)}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
