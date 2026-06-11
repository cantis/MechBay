from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import structlog
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


logger = structlog.get_logger()


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)
db_session = scoped_session(SessionLocal)


def init_db(app: Flask) -> None:
    """Initialize SQLAlchemy engine/session and create tables."""
    global engine
    engine = create_engine(app.config["DATABASE_URL"], future=True)
    SessionLocal.configure(bind=engine)

    # Import models package so all tables are registered before create_all
    from .models import miniature  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_schema_constraints(engine)

    @app.teardown_appcontext
    def remove_session(exception: Exception | None) -> None:  # noqa: ARG001
        db_session.remove()


def _apply_schema_constraints(db_engine) -> None:
    """Apply database constraints not expressible via SQLAlchemy models alone."""
    dialect_name = db_engine.dialect.name
    index_sql = None

    if dialect_name == "sqlite":
        index_sql = (
            'CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_force '
            'ON "forces"(is_active) WHERE is_active = 1'
        )
    elif dialect_name == "postgresql":
        index_sql = (
            'CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_force '
            'ON "forces"(is_active) WHERE is_active IS TRUE'
        )

    if index_sql is not None:
        with db_engine.connect() as conn:
            conn.execute(text(index_sql))
            conn.commit()
        logger.info("schema_constraint_applied", constraint="uix_one_active_force")


@contextmanager
def session_scope() -> Iterator:
    """Provide a transactional scope around a series of operations."""
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.error("db_rollback", exc_info=True)
        raise
    finally:
        session.close()
