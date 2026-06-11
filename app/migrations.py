"""Database migrations for MechBay."""

from __future__ import annotations

from flask import Flask

from .config import Config


def run_migrations():
    """Create all tables and apply schema constraints via init_db."""
    app = Flask(__name__)
    app.config.from_object(Config())

    from .extensions import init_db

    init_db(app)

    print("Database tables created successfully")


if __name__ == "__main__":
    run_migrations()
