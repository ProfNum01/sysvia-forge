"""Explicit local synthetic seed, without inspection results."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import Settings
from backend.app.models.database import Base, connect_database
from backend.app.services.seed import seed_demo

if __name__ == "__main__":
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine, sessions = connect_database(settings.database_url)
    Base.metadata.create_all(engine)
    with sessions() as db:
        created = seed_demo(db)
    engine.dispose()
    print("Synthetic demo orders and inventory seeded." if created else "Seed skipped; existing order data was preserved.")
