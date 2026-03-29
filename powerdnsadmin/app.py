"""
PowerDNS-AdminNG FastAPI application.

This is the primary application entry point. The Next.js SPA handles all
UI rendering — FastAPI provides API v1/v2 endpoints, server-side callbacks
(OAuth/SAML/DynDNS), and middleware (sessions, security headers).
"""
import logging
import os

from fastapi import FastAPI

from powerdnsadmin.core.config import get_config
from powerdnsadmin.models.base import db


def _ensure_db_seed():
    """Create tables and seed required rows (roles) if they don't exist."""
    from powerdnsadmin.models.base import db as _db
    from powerdnsadmin.models.role import Role

    _db.metadata.create_all(bind=_db.engine)

    existing = _db.session.query(Role).count()
    if existing == 0:
        _db.session.add_all([
            Role(name='Administrator', description='Administrator'),
            Role(name='User', description='User'),
            Role(name='Operator', description='Operator'),
        ])
        _db.session.commit()
        logging.getLogger(__name__).info("Seeded default roles")


def create_app(config=None):
    """Create the FastAPI application.

    Args:
        config: Optional config override (dict or .py file path).

    Returns:
        Configured FastAPI application.
    """
    # Load configuration
    app_config = get_config(config)

    # Set up logging
    log_level_name = os.environ.get('PDNS_ADMIN_LOG_LEVEL', 'WARNING')
    log_level = logging.getLevelName(log_level_name.upper())
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(filename)s:%(lineno)d] %(levelname)s - %(message)s"
    )

    # Initialize database
    db.init_db(
        app_config['SQLALCHEMY_DATABASE_URI'],
        pool_recycle=300,
        pool_pre_ping=True,
    )

    # Import all models to register them with metadata
    import powerdnsadmin.models  # noqa: F401

    # Ensure tables and seed data exist (for fresh DBs without migrations)
    _ensure_db_seed()

    # Create FastAPI app
    from .api.v1 import router as api_v1_router
    from .api.v2 import router as api_v2_router
    from .web.callbacks import router as callbacks_router

    fastapi_app = FastAPI(
        title="PowerDNS-Admin API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Store config for access in route handlers
    fastapi_app.state.config = app_config

    # Include routers
    fastapi_app.include_router(api_v1_router)
    fastapi_app.include_router(api_v2_router)
    fastapi_app.include_router(callbacks_router)

    # Set up middleware and error handlers
    from .web.middleware import setup_middleware
    from .web.errors import register_error_handlers
    setup_middleware(fastapi_app, app_config)
    register_error_handlers(fastapi_app)

    return fastapi_app
