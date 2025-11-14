"""Database migrations for MechBay."""

from __future__ import annotations

from flask import Flask

from .config import Config


def run_migrations():
    """Create all tables defined in models."""
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
    print("Database tables created successfully")


if __name__ == "__main__":
    run_migrations()
