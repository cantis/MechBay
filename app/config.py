from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    # Database URL, default to sqlite file inside app folder
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}")
    JSON_SORT_KEYS = False


class TestingConfig(Config):
    TESTING = True
    # Use in-memory SQLite for tests
    DATABASE_URL = "sqlite+pysqlite:///:memory:"
