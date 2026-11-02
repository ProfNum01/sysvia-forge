"""Install the reviewed v2 synthetic IMG references into the local catalog."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import Settings
from backend.app.models.database import connect_database
from backend.app.services.img_reference_registration import install_img_references


if __name__ == "__main__":
    settings = Settings.from_env()
    engine, sessions = connect_database(settings.database_url)
    try:
        with sessions() as db:
            changed = install_img_references(
                db, settings.data_dir, ROOT / "evaluation/datasets/img-reference-v2")
        print(f"Installed {changed} new synthetic product references; no inspection records changed")
    finally:
        engine.dispose()
