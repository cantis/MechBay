from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
from flask import Flask

# Ensure project root is on sys.path for 'import app'
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover - defensive
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions import Base, engine  # noqa: E402


@pytest.fixture()
def app() -> Flask:
    # Temporary file-based SQLite for persistence across requests in a test
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    test_app = create_app()
    test_app.config.update({"TESTING": True})
    yield test_app

    # Teardown
    if engine:
        Base.metadata.drop_all(bind=engine)
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def mini_data():
    return {
        "unique_id": "WHM-001",
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
        "status": "New",
        "tray_id": "T1",
        "notes": "First test mini",
    }
