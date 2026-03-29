"""Database session management.

Delegates to the standalone SQLAlchemy shim in models.base.
During the dual-mount period, both Flask and FastAPI routes share
the same engine and scoped session.
"""
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def init_db(database_uri: str, engine_options: dict | None = None) -> None:
    """Initialize the database engine (delegates to models.base.db)."""
    from powerdnsadmin.models.base import db
    db.init_db(database_uri, **(engine_options or {}))


def get_engine():
    """Return the SQLAlchemy engine."""
    from powerdnsadmin.models.base import db
    return db.engine


def get_session_factory():
    """Return the session factory."""
    from powerdnsadmin.models.base import db
    return db.session.session_factory


async def get_db():
    """FastAPI dependency that yields a database session.

    Usage:
        @router.get("/example")
        async def example(db: Session = Depends(get_db)):
            ...
    """
    from powerdnsadmin.models.base import db
    session = db.session()
    try:
        yield session
    finally:
        db.session.remove()
