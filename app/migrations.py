"""Database migrations for MechBay."""

from __future__ import annotations

from flask import Flask
from sqlalchemy import text

from .config import Config


def run_migrations():
    """Create all tables defined in models and apply schema constraints."""
    # Create minimal Flask app to initialize DB
    app = Flask(__name__)
    app.config.from_object(Config())

    from .extensions import init_db

    init_db(app)

    # Import models to ensure they're registered
    from .extensions import Base, engine
    from .models import (  # noqa: F401
        Force,
        ForceMiniature,
        Lance,
        LanceTemplate,
        LanceTemplateMiniature,
        Miniature,
    )

    Base.metadata.create_all(bind=engine)

    # Enforce single-active-force constraint at the database level.
    # SQLite supports partial unique indexes: only one row may have is_active = 1.
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_force "
                "ON force(is_active) WHERE is_active = 1"
            )
        )
        conn.commit()

    print("Database tables created successfully")


if __name__ == "__main__":
    run_migrations()
