"""
FastAPI application with Flask mounted via WSGIMiddleware.

During the migration period, FastAPI handles /api/v1/ routes while
Flask continues to serve the web UI and legacy API endpoints.
Once all API endpoints are migrated, the Flask routes for /api/v1/
will be removed.
"""
from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware

from .api.v1 import router as api_v1_router


def create_app(config=None):
    """Create the combined FastAPI + Flask application.

    Args:
        config: Optional config path or dict, passed to Flask's create_app().

    Returns:
        FastAPI application with Flask mounted as WSGI sub-app.
    """
    # Import Flask factory here to avoid circular imports
    from powerdnsadmin import create_app as create_flask_app

    flask_app = create_flask_app(config)

    fastapi_app = FastAPI(
        title="PowerDNS-Admin API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Store Flask app reference for access in dependencies
    fastapi_app.state.flask_app = flask_app

    # Include FastAPI API routers
    fastapi_app.include_router(api_v1_router)

    # Mount Flask as fallback for all non-FastAPI routes
    # This MUST be last -- it catches everything FastAPI doesn't handle
    fastapi_app.mount("/", WSGIMiddleware(flask_app))

    return fastapi_app
