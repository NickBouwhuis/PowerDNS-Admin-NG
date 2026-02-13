"""Tests for FastAPI + Flask dual-mount application."""
import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.wsgi import WSGIMiddleware
    from powerdnsadmin.api.v1 import router as api_v1_router
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.fixture(scope="module")
def fastapi_client(app):
    """Build a FastAPI app wrapping the shared Flask app fixture."""
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed")

    fastapi_app = FastAPI(
        title="PowerDNS-Admin API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    fastapi_app.state.flask_app = app
    fastapi_app.include_router(api_v1_router)
    fastapi_app.mount("/", WSGIMiddleware(app))

    return TestClient(fastapi_app, raise_server_exceptions=False)


class TestDualMount:
    """Verify FastAPI and Flask coexist correctly."""

    def test_fastapi_health(self, fastapi_client):
        """FastAPI health endpoint is reachable."""
        resp = fastapi_client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_fastapi_openapi(self, fastapi_client):
        """FastAPI auto-generates OpenAPI spec."""
        resp = fastapi_client.get("/api/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["title"] == "PowerDNS-Admin API"
        assert "/api/v1/health" in data["paths"]

    def test_flask_routes_reachable(self, fastapi_client):
        """Flask web UI routes are reachable through the mount.

        The login page may fail to render fully in test (missing
        template assets), but we verify Flask receives the request
        by checking for a non-404 response.
        """
        resp = fastapi_client.get("/login", follow_redirects=False)
        # Any response except 404 proves Flask received the request
        assert resp.status_code != 404

    def test_flask_api_version(self, fastapi_client):
        """Flask's /api endpoint (version listing) still works."""
        resp = fastapi_client.get("/api")
        # This may return 200 or redirect depending on Flask config
        assert resp.status_code in (200, 301, 302, 308)
