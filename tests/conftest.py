from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on sys.path for 'import app'
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover - defensive
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture(scope="function")
def app():
    """
    Create a test Flask app with an isolated temporary SQLite database.
    CRITICAL: Uses a temporary file database to ensure complete isolation from production data.
    The temp file is created in the system temp directory and deleted after the test.
    """
    # Create a temporary database file in the system temp directory
    # This ensures we NEVER touch production data
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="mechbay_test_")
    os.close(db_fd)

    # Save original DATABASE_URL and set test database
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Create the test app
    test_app = create_app()
    test_app.config.update({"TESTING": True})

    yield test_app

    # Teardown - clean up sessions, engine, and temp file
    from app.extensions import Base, db_session
    from app.extensions import engine as db_engine

    try:
        db_session.remove()
    except Exception:
        pass

    try:
        if db_engine:
            Base.metadata.drop_all(bind=db_engine)
            db_engine.dispose()
    except Exception:
        pass

    # Delete the temporary database file
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass

    # Restore original DATABASE_URL or remove if it didn't exist
    if original_db_url is not None:
        os.environ["DATABASE_URL"] = original_db_url
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


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
