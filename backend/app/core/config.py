from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    data_dir: Path = ROOT / "data"
    operator_token: str = field(default="", repr=False)
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    max_upload_bytes: int = 15 * 1024 * 1024

    @classmethod
    def from_env(cls):
        location = Path(os.environ.get("PROOFSIGHT_ENV_FILE", str(ROOT / ".env"))).expanduser()
        load_dotenv(location, override=False, interpolate=False, encoding="utf-8-sig")
        data_dir = Path(os.getenv("PROOFSIGHT_DATA_DIR", str(ROOT / "data"))).resolve()
        return cls(
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'proofsight.db'}"),
            data_dir=data_dir,
            operator_token=os.getenv("OPERATOR_TOKEN", ""),
            cors_origins=tuple(x.strip() for x in os.getenv(
                "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if x.strip()),
        )
