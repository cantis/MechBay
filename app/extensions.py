from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)
db_session = scoped_session(SessionLocal)


def init_db(app: Flask) -> None:
    """Initialize SQLAlchemy engine/session and create tables."""
    global engine
    engine = create_engine(app.config["DATABASE_URL"], future=True)
    SessionLocal.configure(bind=engine)

    # Import models to register metadata before create_all
    from .models import miniature  # noqa: F401

    Base.metadata.create_all(bind=engine)

    @app.teardown_appcontext
    def remove_session(exception: Exception | None) -> None:  # noqa: ARG001
        db_session.remove()


@contextmanager
def session_scope() -> Iterator:
    """Provide a transactional scope around a series of operations."""
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        raise
    finally:
        session.close()
