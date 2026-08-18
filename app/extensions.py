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
    _apply_schema_migrations(engine)

    @app.teardown_appcontext
    def remove_session(exception: Exception | None) -> None:  # noqa: ARG001
        db_session.remove()


def _apply_schema_constraints(db_engine) -> None:
    """Apply database constraints not expressible via SQLAlchemy models alone."""
    dialect_name = db_engine.dialect.name
    indexes: list[tuple[str, str]] = []
    if dialect_name == "sqlite":
        indexes = [
            (
                "uix_one_active_force",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_force "
                'ON "forces"(is_active) WHERE is_active = 1',
            ),
            (
                "uix_one_active_campaign",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_campaign "
                'ON "campaigns"(is_active) WHERE is_active = 1',
            ),
            (
                "uix_one_active_contract",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_contract "
                "ON \"contracts\"(campaign_id) WHERE status = 'active'",
            ),
        ]
    elif dialect_name == "postgresql":
        indexes = [
            (
                "uix_one_active_force",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_force "
                'ON "forces"(is_active) WHERE is_active IS TRUE',
            ),
            (
                "uix_one_active_campaign",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_campaign "
                'ON "campaigns"(is_active) WHERE is_active IS TRUE',
            ),
            (
                "uix_one_active_contract",
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_one_active_contract "
                "ON \"contracts\"(campaign_id) WHERE status = 'active'",
            ),
        ]

    if indexes:
        with db_engine.connect() as conn:
            for name, index_sql in indexes:
                conn.execute(text(index_sql))
                logger.info("schema_constraint_applied", constraint=name)
            conn.commit()


def _apply_schema_migrations(db_engine) -> None:
    """Apply additive column migrations for existing databases."""
    if db_engine.dialect.name != "sqlite":
        return

    with db_engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(forces)")).fetchall()}
        if "inventory_faction" not in columns:
            conn.execute(text('ALTER TABLE "forces" ADD COLUMN inventory_faction VARCHAR(64)'))
            conn.commit()
            logger.info("schema_migration_applied", table="forces", column="inventory_faction")

        lance_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(lances)")).fetchall()
        }
        if "header_color" not in lance_columns:
            conn.execute(text('ALTER TABLE "lances" ADD COLUMN header_color VARCHAR(7)'))
            conn.commit()
            logger.info("schema_migration_applied", table="lances", column="header_color")

        campaign_tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "campaigns" in campaign_tables:
            campaign_columns = {
                row[1] for row in conn.execute(text("PRAGMA table_info(campaigns)")).fetchall()
            }
            campaign_adds = {
                "mul_faction_id": "INTEGER",
                "mul_era_id": "INTEGER",
                "mul_faction_name": "VARCHAR(128)",
                "mul_era_name": "VARCHAR(128)",
            }
            for column, col_type in campaign_adds.items():
                if column not in campaign_columns:
                    conn.execute(text(f'ALTER TABLE "campaigns" ADD COLUMN {column} {col_type}'))
                    conn.commit()
                    logger.info("schema_migration_applied", table="campaigns", column=column)

        if "travel_events" in campaign_tables:
            travel_columns = {
                row[1] for row in conn.execute(text("PRAGMA table_info(travel_events)")).fetchall()
            }
            if "contract_id" not in travel_columns:
                conn.execute(text('ALTER TABLE "travel_events" ADD COLUMN contract_id INTEGER'))
                conn.commit()
                logger.info("schema_migration_applied", table="travel_events", column="contract_id")


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
