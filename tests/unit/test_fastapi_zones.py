"""Unit tests for FastAPI zone and server API endpoints.

Tests powerdnsadmin/api/v1/zones.py and powerdnsadmin/api/v1/servers.py
using the FastAPI TestClient with mocked Flask app context, database models,
and PowerDNS API calls.

Because the route handlers use deferred (local) imports such as
``from powerdnsadmin.models.domain import Domain``, we must patch at the
*source* module path rather than on the route module itself.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

from powerdnsadmin.api.v1 import router as api_v1_router
from powerdnsadmin.api.deps import (
    get_current_user,
    get_current_apikey,
    user_can_create_domain,
    get_current_user_or_apikey,
)


# ---------------------------------------------------------------------------
# Patch targets (source module paths for deferred imports)
# ---------------------------------------------------------------------------

_DOMAIN = "powerdnsadmin.models.domain.Domain"
_DOMAIN_USER = "powerdnsadmin.models.domain.DomainUser"
_ACCOUNT = "powerdnsadmin.models.account.Account"
_ACCOUNT_USER = "powerdnsadmin.models.account.AccountUser"
_SETTING = "powerdnsadmin.models.setting.Setting"
_HISTORY = "powerdnsadmin.models.history.History"
_DB = "powerdnsadmin.models.base.db"
_ZONE_SUMMARY = "powerdnsadmin.schemas.zone.ZoneSummary"
_UTILS = "powerdnsadmin.lib.utils"
_PDNS_CLIENT = "powerdnsadmin.services.pdns_client.PowerDNSClient"
_FORWARD_TO_PDNS = "powerdnsadmin.api.v1.servers.forward_to_pdns"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(role_name="Administrator", username="admin", user_id=1):
    """Create a mock user with role, username, and id."""
    user = MagicMock()
    user.role.name = role_name
    user.username = username
    user.id = user_id
    return user


def _make_mock_apikey(role_name="Administrator", description="test-key",
                      domains=None, accounts=None):
    """Create a mock API key with role, description, domains, and accounts."""
    apikey = MagicMock()
    apikey.role.name = role_name
    apikey.description = description
    apikey.domains = domains if domains is not None else []
    apikey.accounts = accounts if accounts is not None else []
    return apikey


def _make_mock_domain(domain_id, name):
    """Create a mock domain with id and name attributes."""
    domain = MagicMock()
    domain.id = domain_id
    domain.name = name
    return domain



def _setting_get_side_effect(key):
    """Default Setting().get() side effect returning common config values."""
    return {
        "pdns_api_url": "http://localhost:8081",
        "pdns_api_key": "test-key",
        "pdns_version": "4.1.0",
        "verify_ssl_connections": False,
    }.get(key)


def _make_pdns_response(data, status_code=200):
    """Create a Response matching what forward_to_pdns returns."""
    return Response(
        content=json.dumps(data).encode() if data is not None else b"",
        status_code=status_code,
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _cache_request_body(request: Request):
    """Dependency that pre-reads the request body.

    Calling ``await request.body()`` populates ``request._body`` so that
    sync route handlers can access it via ``request._body``.
    """
    await request.body()


@pytest.fixture
def app_and_client():
    """Build a FastAPI TestClient with the full router and a mock Flask app.

    Returns a tuple of (fastapi_app, client) so tests can set
    dependency_overrides on the app.
    """
    fastapi_app = FastAPI(dependencies=[Depends(_cache_request_body)])
    fastapi_app.include_router(api_v1_router)

    client = TestClient(fastapi_app, raise_server_exceptions=False)
    yield fastapi_app, client

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()


# ===========================================================================
# Zone endpoints (Basic auth) - /api/v1/pdnsadmin/zones
# ===========================================================================

class TestListZones:
    """Tests for GET /api/v1/pdnsadmin/zones."""

    @patch(_ZONE_SUMMARY)
    @patch(_DOMAIN)
    def test_admin_gets_all_zones(self, MockDomain, MockZoneSummary, app_and_client):
        """Admin user gets all zones from Domain.query.all()."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[get_current_user] = lambda: mock_user

        domain1 = _make_mock_domain(1, "example.com")
        domain2 = _make_mock_domain(2, "example.org")
        MockDomain.query.all.return_value = [domain1, domain2]

        def mock_validate(d):
            summary = MagicMock()
            summary.model_dump.return_value = {"id": d.id, "name": d.name}
            return summary

        MockZoneSummary.model_validate.side_effect = mock_validate

        resp = client.get("/api/v1/pdnsadmin/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "example.com"
        assert data[1]["name"] == "example.org"

    @patch(_DB)
    @patch(_ACCOUNT_USER)
    @patch(_ACCOUNT)
    @patch(_DOMAIN_USER)
    @patch(_ZONE_SUMMARY)
    @patch(_DOMAIN)
    def test_user_gets_only_assigned_zones(self, MockDomain, MockZoneSummary,
                                           MockDomainUser, MockAccount,
                                           MockAccountUser, MockDb,
                                           app_and_client):
        """Non-admin user gets only their assigned zones."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="User", username="regular", user_id=2)
        app.dependency_overrides[get_current_user] = lambda: mock_user

        # Mock the DB query chain for _get_user_domains
        domain1 = _make_mock_domain(1, "myzone.com")
        MockDb.session.query.return_value \
            .outerjoin.return_value \
            .outerjoin.return_value \
            .outerjoin.return_value \
            .filter.return_value \
            .all.return_value = [domain1]

        def mock_validate(d):
            summary = MagicMock()
            summary.model_dump.return_value = {"id": d.id, "name": d.name}
            return summary

        MockZoneSummary.model_validate.side_effect = mock_validate

        resp = client.get("/api/v1/pdnsadmin/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "myzone.com"


class TestCreateZone:
    """Tests for POST /api/v1/pdnsadmin/zones."""

    @patch(_UTILS)
    @patch(_PDNS_CLIENT)
    @patch(_HISTORY)
    @patch(_DOMAIN)
    @patch(_SETTING)
    def test_create_zone_success(self, MockSetting, MockDomain, MockHistory,
                                 MockPdnsClient, mock_utils, app_and_client):
        """Creating a zone returns 201 when PowerDNS returns 201."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[user_can_create_domain] = lambda: mock_user

        # Mock Setting
        setting_instance = MagicMock()
        setting_instance.get.side_effect = _setting_get_side_effect
        MockSetting.return_value = setting_instance

        # Mock utils
        mock_utils.pdns_api_extended_uri.return_value = "/api/v1"
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.content = json.dumps(
            {"name": "newzone.com.", "kind": "Native"}
        ).encode()
        mock_utils.fetch_remote.return_value = mock_resp

        # Mock Domain
        domain_instance = MagicMock()
        domain_instance.get_id_by_name.return_value = 10
        MockDomain.return_value = domain_instance

        # Mock History
        history_instance = MagicMock()
        MockHistory.return_value = history_instance

        body = {
            "name": "newzone.com.",
            "kind": "Native",
            "nameservers": ["ns1.newzone.com."],
        }
        resp = client.post("/api/v1/pdnsadmin/zones", content=json.dumps(body))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "newzone.com."

    @patch(_UTILS)
    @patch(_PDNS_CLIENT)
    @patch(_DOMAIN)
    @patch(_SETTING)
    def test_create_zone_conflict(self, MockSetting, MockDomain,
                                  MockPdnsClient, mock_utils, app_and_client):
        """Creating a zone that already exists returns 409."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[user_can_create_domain] = lambda: mock_user

        setting_instance = MagicMock()
        setting_instance.get.side_effect = _setting_get_side_effect
        MockSetting.return_value = setting_instance

        mock_utils.pdns_api_extended_uri.return_value = "/api/v1"
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.content = json.dumps({"error": "Conflict"}).encode()
        mock_utils.fetch_remote.return_value = mock_resp

        body = {"name": "existing.com.", "kind": "Native"}
        resp = client.post("/api/v1/pdnsadmin/zones", content=json.dumps(body))
        assert resp.status_code == 409


class TestDeleteZone:
    """Tests for DELETE /api/v1/pdnsadmin/zones/{domain_name}."""

    @patch(_UTILS)
    @patch(_HISTORY)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_DOMAIN)
    def test_delete_zone_success(self, MockDomain, MockSetting, MockDb,
                                 MockHistory, mock_utils, app_and_client):
        """Deleting an existing zone returns 204."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[user_can_create_domain] = lambda: mock_user

        # Mock Domain.query.filter for the lookup
        domain_obj = _make_mock_domain(1, "deleteme.com")
        MockDomain.query.filter.return_value.first.return_value = domain_obj

        # Mock Setting
        setting_instance = MagicMock()
        setting_instance.get.side_effect = _setting_get_side_effect
        MockSetting.return_value = setting_instance

        # Mock utils
        mock_utils.pdns_api_extended_uri.return_value = "/api/v1"
        mock_utils.pretty_domain_name.return_value = "deleteme.com"
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_utils.fetch_remote.return_value = mock_resp

        # Mock Domain() for domain update/get_id_by_name
        new_domain_instance = MagicMock()
        new_domain_instance.get_id_by_name.return_value = 1
        MockDomain.return_value = new_domain_instance

        # Mock History
        history_instance = MagicMock()
        MockHistory.return_value = history_instance

        resp = client.delete("/api/v1/pdnsadmin/zones/deleteme.com")
        assert resp.status_code == 204

    @patch(_DOMAIN)
    def test_delete_zone_not_found(self, MockDomain, app_and_client):
        """Deleting a non-existent zone returns 404."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[user_can_create_domain] = lambda: mock_user

        MockDomain.query.filter.return_value.first.return_value = None

        resp = client.delete("/api/v1/pdnsadmin/zones/nosuchzone.com")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch(_DB)
    @patch(_ACCOUNT_USER)
    @patch(_ACCOUNT)
    @patch(_DOMAIN_USER)
    @patch(_DOMAIN)
    def test_delete_zone_access_forbidden_for_user(
        self, MockDomain, MockDomainUser, MockAccount,
        MockAccountUser, MockDb, app_and_client
    ):
        """Non-admin user without access to the zone gets 403."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="User", username="regular", user_id=2)
        app.dependency_overrides[user_can_create_domain] = lambda: mock_user

        # The zone exists
        domain_obj = _make_mock_domain(1, "protected.com")
        MockDomain.query.filter.return_value.first.return_value = domain_obj

        # _get_user_domains returns empty list (user has no domains)
        MockDb.session.query.return_value \
            .outerjoin.return_value \
            .outerjoin.return_value \
            .outerjoin.return_value \
            .filter.return_value \
            .all.return_value = []

        resp = client.delete("/api/v1/pdnsadmin/zones/protected.com")
        assert resp.status_code == 403
        assert "not allowed" in resp.json()["detail"].lower()


# ===========================================================================
# Server pass-through endpoints (API key auth) - /api/v1/servers/...
# ===========================================================================

class TestGetZonesServerEndpoint:
    """Tests for GET /api/v1/servers/{server_id}/zones."""

    @patch(_ZONE_SUMMARY)
    @patch(_DOMAIN)
    def test_pdnsadmin_server_returns_local_db_zones(
        self, MockDomain, MockZoneSummary, app_and_client
    ):
        """GET /api/v1/servers/pdnsadmin/zones returns zones from local DB for admin."""
        app, client = app_and_client

        mock_apikey = _make_mock_apikey(role_name="Administrator")
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        domain1 = _make_mock_domain(1, "example.com")
        domain2 = _make_mock_domain(2, "example.org")
        MockDomain.query.all.return_value = [domain1, domain2]

        def mock_validate(d):
            summary = MagicMock()
            summary.model_dump.return_value = {"id": d.id, "name": d.name}
            return summary

        MockZoneSummary.model_validate.side_effect = mock_validate

        resp = client.get("/api/v1/servers/pdnsadmin/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "example.com"
        assert data[1]["name"] == "example.org"

    @patch(_FORWARD_TO_PDNS)
    def test_other_server_forwards_to_pdns(self, mock_forward, app_and_client):
        """GET /api/v1/servers/localhost/zones forwards to PowerDNS."""
        app, client = app_and_client

        mock_apikey = _make_mock_apikey(role_name="Administrator")
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        zones_data = [
            {"name": "fwd1.com.", "kind": "Native"},
            {"name": "fwd2.com.", "kind": "Master"},
        ]
        mock_forward.return_value = _make_pdns_response(zones_data)

        resp = client.get("/api/v1/servers/localhost/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "fwd1.com."

    @patch(_FORWARD_TO_PDNS)
    def test_user_role_filters_zones(self, mock_forward, app_and_client):
        """GET /api/v1/servers/localhost/zones filters zones for User role API key."""
        app, client = app_and_client

        # User API key with access to only one domain
        user_domain = _make_mock_domain(1, "allowed.com")
        mock_apikey = _make_mock_apikey(
            role_name="User",
            domains=[user_domain],
            accounts=[],
        )
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        all_zones = [
            {"name": "allowed.com.", "kind": "Native"},
            {"name": "forbidden.com.", "kind": "Native"},
            {"name": "other.com.", "kind": "Master"},
        ]
        mock_forward.return_value = _make_pdns_response(all_zones)

        resp = client.get("/api/v1/servers/localhost/zones")
        assert resp.status_code == 200
        data = resp.json()
        # Only "allowed.com." should remain (trailing dot stripped matches "allowed.com")
        assert len(data) == 1
        assert data[0]["name"] == "allowed.com."

    @patch(_ZONE_SUMMARY)
    @patch(_DOMAIN)
    def test_pdnsadmin_server_user_role_returns_apikey_domains(
        self, MockDomain, MockZoneSummary, app_and_client
    ):
        """GET /api/v1/servers/pdnsadmin/zones for User returns only apikey.domains."""
        app, client = app_and_client

        user_domain = _make_mock_domain(1, "myzone.com")
        mock_apikey = _make_mock_apikey(
            role_name="User",
            domains=[user_domain],
        )
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        def mock_validate(d):
            summary = MagicMock()
            summary.model_dump.return_value = {"id": d.id, "name": d.name}
            return summary

        MockZoneSummary.model_validate.side_effect = mock_validate

        resp = client.get("/api/v1/servers/pdnsadmin/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "myzone.com"
        # Domain.query.all() should NOT have been called for User role
        MockDomain.query.all.assert_not_called()


class TestListServers:
    """Tests for GET /api/v1/servers."""

    @patch(_FORWARD_TO_PDNS)
    def test_list_servers_forwards_to_pdns(self, mock_forward, app_and_client):
        """GET /api/v1/servers forwards to PowerDNS API."""
        app, client = app_and_client

        mock_apikey = _make_mock_apikey(role_name="Administrator")
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        servers_data = [
            {"type": "Server", "id": "localhost", "url": "/api/v1/servers/localhost"},
        ]
        mock_forward.return_value = _make_pdns_response(servers_data)

        resp = client.get("/api/v1/servers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "localhost"


class TestSyncDomains:
    """Tests for GET /api/v1/sync_domains."""

    @patch(_DOMAIN)
    def test_sync_domains_triggers_update(self, MockDomain, app_and_client):
        """GET /api/v1/sync_domains triggers Domain().update() and returns message."""
        app, client = app_and_client

        mock_user = _make_mock_user(role_name="Administrator")
        app.dependency_overrides[get_current_user_or_apikey] = lambda: mock_user

        domain_instance = MagicMock()
        MockDomain.return_value = domain_instance

        resp = client.get("/api/v1/sync_domains")
        assert resp.status_code == 200
        assert "synchronization" in resp.json().lower()
        domain_instance.update.assert_called_once()

    @patch(_DOMAIN)
    def test_sync_domains_with_apikey(self, MockDomain, app_and_client):
        """GET /api/v1/sync_domains works with API key auth as well."""
        app, client = app_and_client

        mock_apikey = _make_mock_apikey(role_name="Operator")
        app.dependency_overrides[get_current_user_or_apikey] = lambda: mock_apikey

        domain_instance = MagicMock()
        MockDomain.return_value = domain_instance

        resp = client.get("/api/v1/sync_domains")
        assert resp.status_code == 200
        domain_instance.update.assert_called_once()


class TestGetServer:
    """Tests for GET /api/v1/servers/{server_id}."""

    @patch(_FORWARD_TO_PDNS)
    def test_get_server_forwards_to_pdns(self, mock_forward, app_and_client):
        """GET /api/v1/servers/localhost forwards to PowerDNS API."""
        app, client = app_and_client

        mock_apikey = _make_mock_apikey(role_name="Administrator")
        app.dependency_overrides[get_current_apikey] = lambda: mock_apikey

        server_data = {
            "type": "Server",
            "id": "localhost",
            "daemon_type": "authoritative",
        }
        mock_forward.return_value = _make_pdns_response(server_data)

        resp = client.get("/api/v1/servers/localhost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "localhost"
        assert data["daemon_type"] == "authoritative"
