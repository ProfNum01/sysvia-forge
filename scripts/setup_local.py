"""Create missing local configuration without overwriting existing values."""
from pathlib import Path
import secrets
from dotenv import dotenv_values, set_key

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / ".env"
    values = dotenv_values(path) if path.exists() else {}
    if not path.exists():
        path.write_text("# Local secrets; excluded from Git.\n", encoding="utf-8")
    if "MODEL_API_KEY" not in values:
        set_key(str(path), "MODEL_API_KEY", "")
    if not values.get("OPERATOR_TOKEN"):
        set_key(str(path), "OPERATOR_TOKEN", secrets.token_urlsafe(36))
    print("Local .env is ready. Populate MODEL_API_KEY locally; credentials were not printed.")
