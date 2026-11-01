"""Explicit local synthetic seed, without inspection results."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.models.database import Base, connect_database
from backend.app.services.seed import seed_demo, seed_packing_demo

if __name__ == "__main__":
    import argparse
    from sqlalchemy import select, delete
    from backend.app.models.database import Order, OrderItem, Inspection, CorrectiveAction, AuditEvent, PickingTask, RemovalTask

    parser = argparse.ArgumentParser(description="Explicit local synthetic seed")
    parser.add_argument("--reset", action="store_true", help="Safely reset synthetic demo records without touching unrelated data")
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine, sessions = connect_database(settings.database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        if args.reset:
            # Safely clear only synthetic demo data
            synthetic_order_ids = list(db.scalars(select(Order.id).where(Order.data_source == "synthetic_seed")))
            if synthetic_order_ids:
                inspection_ids = list(db.scalars(select(Inspection.id).where(Inspection.order_id.in_(synthetic_order_ids))))
                if inspection_ids:
                    db.execute(delete(CorrectiveAction).where(CorrectiveAction.inspection_id.in_(inspection_ids)))
                    db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_(inspection_ids)))
                db.execute(delete(PickingTask).where(PickingTask.order_id.in_(synthetic_order_ids)))
                db.execute(delete(RemovalTask).where(RemovalTask.order_id.in_(synthetic_order_ids)))
                db.execute(delete(Inspection).where(Inspection.order_id.in_(synthetic_order_ids)))
                db.execute(delete(OrderItem).where(OrderItem.order_id.in_(synthetic_order_ids)))
                db.execute(delete(Order).where(Order.id.in_(synthetic_order_ids)))
                db.commit()
                print("Synthetic demo orders reset.")
        created = seed_demo(db)
        packing_created = seed_packing_demo(db)
    engine.dispose()
    print("Synthetic demo orders and inventory seeded." if created else "Seed skipped; existing order data was preserved.")
    print("Synthetic packing orders seeded." if packing_created else "Synthetic packing orders already exist.")
