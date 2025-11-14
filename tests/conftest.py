from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for 'import app'
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover - defensive
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture(scope="function")
def app():
    """Provide a fresh Flask app backed by an in-memory SQLite database per test.

    Using an in-memory database ensures tests never touch or clear production data.
    The schema is created at app init and discarded automatically when the engine
    is disposed at test end.
    """
    test_app = create_app({
        "TESTING": True,
        # pysqlite driver explicit for consistency; plain sqlite:///:memory: also works
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    })
    return test_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def mini_data():
    return {
        "unique_id": 1001,
        "prefix": "WHM",
        "chassis": "Warhammer",
        "type": "Mech",
        "status": "New",
        "tray_id": "T1",
        "notes": "First test mini",
    }
