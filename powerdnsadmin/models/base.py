"""Standalone SQLAlchemy compatibility shim replacing Flask-SQLAlchemy.

Provides a `db` singleton with the same API surface used throughout the
codebase: db.Model, db.Column, db.Integer, db.session, db.or_, etc.
No Flask dependency required.
"""
import logging

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

logger = logging.getLogger(__name__)


class _QueryProperty:
    """Descriptor providing Model.query, matching Flask-SQLAlchemy behavior.

    When accessed on a model class (e.g. User.query), returns a
    Query object bound to the current scoped session.
    """

    def __get__(self, obj, cls):
        return db.session.query(cls)


class _Base(DeclarativeBase):
    """Declarative base for all models."""
    query = _QueryProperty()


class _DatabaseShim:
    """Drop-in replacement for flask_sqlalchemy.SQLAlchemy().

    Exposes the same attribute API that model files and route files
    depend on: db.Model, db.Column, db.Integer, db.session, etc.
    """

    def __init__(self):
        self._engine = None
        self._scoped_session = None

        # Declarative base
        self.Model = _Base

        # Column types (re-exported from sqlalchemy)
        self.Column = sa.Column
        self.Integer = sa.Integer
        self.SmallInteger = sa.SmallInteger
        self.BigInteger = sa.BigInteger
        self.String = sa.String
        self.Text = sa.Text
        self.Boolean = sa.Boolean
        self.DateTime = sa.DateTime
        self.Float = sa.Float
        self.BLOB = sa.LargeBinary
        self.LargeBinary = sa.LargeBinary

        # Constraints and schema objects
        self.ForeignKey = sa.ForeignKey
        self.UniqueConstraint = sa.UniqueConstraint
        self.Index = sa.Index

        # Relationships
        self.relationship = orm.relationship
        self.backref = orm.backref

        # SQL expression helpers
        self.or_ = sa.or_
        self.and_ = sa.and_

    def init_db(self, database_uri, **engine_opts):
        """Initialize the database engine and scoped session.

        Must be called once at application startup before any database access.
        """
        self._engine = sa.create_engine(database_uri, **engine_opts)
        session_factory = sessionmaker(bind=self._engine)
        self._scoped_session = scoped_session(session_factory)
        logger.info(
            "Database initialized: %s",
            database_uri.split("@")[-1] if "@" in database_uri else database_uri
        )

    @property
    def engine(self):
        """Return the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call db.init_db() first.")
        return self._engine

    @property
    def session(self):
        """Return the scoped session proxy."""
        if self._scoped_session is None:
            raise RuntimeError("Database not initialized. Call db.init_db() first.")
        return self._scoped_session

    @property
    def metadata(self):
        """Return the model metadata."""
        return self.Model.metadata

    def Table(self, name, *args, **kwargs):
        """Create a Table bound to the model metadata."""
        return sa.Table(name, self.Model.metadata, *args, **kwargs)

    def create_all(self, bind=None):
        """Create all tables in the database."""
        engine = bind or self.engine
        self.Model.metadata.create_all(engine)

    def drop_all(self, bind=None):
        """Drop all tables from the database."""
        engine = bind or self.engine
        self.Model.metadata.drop_all(engine)


db = _DatabaseShim()

domain_apikey = db.Table(
    'domain_apikey',
    db.Column('domain_id', db.Integer, db.ForeignKey('domain.id')),
    db.Column('apikey_id', db.Integer, db.ForeignKey('apikey.id')))
