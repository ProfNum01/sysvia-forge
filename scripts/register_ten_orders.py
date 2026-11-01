"""Explicitly register the ten local synthetic orders in the configured database."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.models.database import connect_database
from backend.app.services.ten_order_registration import register_ten_orders


if __name__ == "__main__":
    engine, sessions = connect_database(Settings.from_env().database_url)
    try:
        with sessions() as db:
            count = register_ten_orders(db, ROOT / "evaluation/datasets/ten-orders/manifest.json")
        print(f"Registered {count} new synthetic orders; no inspections created")
    finally:
        engine.dispose()
