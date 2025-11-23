from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    # Database URL, default to Windows AppData location
    # For development or custom location, set DATABASE_URL environment variable
    _default_db_path = Path.home() / "AppData" / "Roaming" / "MechBay" / "mechbay.db"
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db_path.as_posix()}")
    JSON_SORT_KEYS = False


class TestingConfig(Config):
    TESTING = True
    # Use in-memory SQLite for tests
    DATABASE_URL = "sqlite+pysqlite:///:memory:"
