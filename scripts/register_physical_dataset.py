"""Validate, then explicitly register an owner-provided physical dataset locally."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.models.database import Base, connect_database
from backend.app.core.migrations import upgrade_local_schema
from backend.app.services.physical_registration import validate_physical_manifest, register_physical_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--register", action="store_true", help="Write an order and product catalog after validation")
    args = parser.parse_args()
    try:
        data = validate_physical_manifest(args.manifest)
    except (ValueError, OSError, KeyError) as exc:
        print(f"BLOCKED: physical dataset validation failed: {type(exc).__name__}")
        return 2
    if not args.register:
        print(f"VALID: {len(data['products'])} owner-registered products, distinct before/after images; no database changes")
        return 0
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine, sessions = connect_database(settings.database_url)
    try:
        Base.metadata.create_all(engine)
        upgrade_local_schema(engine)
        with sessions() as db:
            result = register_physical_manifest(db, args.manifest, settings.data_dir)
        print(f"REGISTERED: {result['products_registered']} products and one order; no inspection or inference created")
        return 0
    except (ValueError, OSError):
        print("BLOCKED: physical dataset could not be registered; existing orders were preserved")
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
