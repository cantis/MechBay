from __future__ import annotations

import os
import secrets
from pathlib import Path

import structlog

BASE_DIR = Path(__file__).resolve().parent
logger = structlog.get_logger()


class Config:
    _secret_key = os.environ.get("SECRET_KEY")
    if _secret_key:
        SECRET_KEY = _secret_key
    else:
        SECRET_KEY = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set - using a randomly generated key. "
            "Sessions will not persist across restarts."
        )

    WTF_CSRF_SECRET_KEY = os.environ.get("WTF_CSRF_SECRET_KEY", SECRET_KEY)
    WTF_CSRF_ENABLED = True
    DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
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
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    # Use in-memory SQLite for tests
    DATABASE_URL = "sqlite+pysqlite:///:memory:"
