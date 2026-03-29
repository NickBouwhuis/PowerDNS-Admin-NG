"""Tests for the FastAPI-only application."""
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from powerdnsadmin.api.v1 import router as api_v1_router


@pytest.fixture(scope="module")
def fastapi_client():
    """Build a FastAPI TestClient with the API router."""
    fastapi_app = FastAPI(
        title="PowerDNS-AdminNG API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    fastapi_app.include_router(api_v1_router)

    return TestClient(fastapi_app, raise_server_exceptions=False)


class TestFastAPIApp:
    """Verify FastAPI application endpoints are reachable."""

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
        assert data["info"]["title"] == "PowerDNS-AdminNG API"
        assert "/api/v1/health" in data["paths"]
