from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    # Database URL, default to Windows AppData location for desktop, /data for Docker
    # For development or custom location, set DATABASE_URL environment variable
    _docker_db_path = Path("/data/mechbay.db")
    _default_db_path = Path.home() / "AppData" / "Roaming" / "MechBay" / "mechbay.db"

    # Use /data if it exists (Docker), otherwise use AppData (Windows desktop)
    if _docker_db_path.parent.exists():
        _db_path = _docker_db_path
    else:
        _db_path = _default_db_path

    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_db_path.as_posix()}")
    JSON_SORT_KEYS = False
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "/")


class TestingConfig(Config):
    TESTING = True
    # Use in-memory SQLite for tests
    DATABASE_URL = "sqlite+pysqlite:///:memory:"
