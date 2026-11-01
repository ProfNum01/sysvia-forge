"""Validate or explicitly register the isolated Claude synthetic test dataset."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.core.migrations import upgrade_local_schema
from backend.app.models.database import Base, connect_database
from backend.app.services.synthetic_registration import validate_synthetic_manifest, register_synthetic_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    try:
        data = validate_synthetic_manifest(args.manifest)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"BLOCKED: synthetic dataset validation failed: {type(exc).__name__}")
        return 2
    if not args.register:
        print(f"VALID: {len(data['products'])} Claude-generated synthetic products; no database changes")
        return 0
    settings = Settings.from_env()
    engine, sessions = connect_database(settings.database_url)
    try:
        Base.metadata.create_all(engine)
        upgrade_local_schema(engine)
        with sessions() as db:
            result = register_synthetic_manifest(db, args.manifest, settings.data_dir)
        print(f"REGISTERED: {result['products_registered']} synthetic products and one test order; no inference created")
        return 0
    except (ValueError, OSError) as exc:
        print(f"BLOCKED: synthetic registration failed: {type(exc).__name__}")
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
