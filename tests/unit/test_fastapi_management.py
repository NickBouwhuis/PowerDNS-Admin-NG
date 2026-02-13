"""Tests for FastAPI user, account, and API key management endpoints.

Tests use the FastAPI TestClient with mocked auth dependencies and
mocked database model operations. No real database or Flask app is needed.

Key implementation details for mocking:

1. **Deferred imports** -- Route handlers import models and schemas inside
   the function body (e.g. ``from powerdnsadmin.models.user import User``).
   Patches must target the *canonical source module* so the deferred import
   picks up the mock:
   - Models:  ``powerdnsadmin.models.<module>.<Class>``
   - Schemas: ``powerdnsadmin.schemas.<Class>``  (re-exported via __init__)

2. **Auth mocking** -- Two different strategies are needed:
   - ``require_role()`` closures reference ``get_current_user`` by name from
     module scope, so ``patch("powerdnsadmin.api.deps.get_current_user")``
     intercepts the call at runtime.
   - ``Depends(get_current_user)`` (used by apikey routes) stores a direct
     reference to the function object.  This requires FastAPI's
     ``app.dependency_overrides[get_current_user]`` mechanism instead.

3. **Request body** -- The sync route handlers read the body via a custom
   ``_get_json_body(request)`` that checks ``request._body`` (not populated
   by TestClient).  We patch ``_get_json_body`` on each route module to
   return the test data dict directly.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from powerdnsadmin.api.v1.users import router as users_router
    from powerdnsadmin.api.v1.accounts import router as accounts_router
    from powerdnsadmin.api.v1.apikeys import router as apikeys_router
    from powerdnsadmin.api.deps import get_current_user as _real_get_current_user

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")


# ---------------------------------------------------------------------------
# Helpers -- mock object factories
# ---------------------------------------------------------------------------

def _make_mock_user(user_id=1, username="admin", role_name="Administrator"):
    """Create a mock user object with the given attributes."""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.firstname = "Admin"
    user.lastname = "User"
    user.email = "admin@example.com"
    user.role = MagicMock()
    user.role.name = role_name
    user.role.id = 1 if role_name == "Administrator" else 2
    user.accounts = []
    return user


def _make_mock_account(account_id=1, name="test-account"):
    """Create a mock account object."""
    acct = MagicMock()
    acct.id = account_id
    acct.name = name
    acct.description = "Test account"
    acct.contact = "contact@example.com"
    acct.mail = "mail@example.com"
    acct.domains = []
    acct.apikeys = []
    return acct


def _make_mock_apikey(key_id=1, description="test key", role_name="Administrator"):
    """Create a mock API key object."""
    apikey = MagicMock()
    apikey.id = key_id
    apikey.description = description
    apikey.role = MagicMock()
    apikey.role.name = role_name
    apikey.role.id = 1
    apikey.domains = []
    apikey.accounts = []
    apikey.key = "hashed-key"
    apikey.plain_key = "plainkey123"
    return apikey


def _build_app_and_client():
    """Build a FastAPI app with the three management routers.

    Returns (app, client).  A mock flask_app is attached to
    ``app.state.flask_app`` so that ``_get_flask_app`` works.
    """
    from fastapi import APIRouter

    app = FastAPI()

    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(users_router)
    api_router.include_router(accounts_router)
    api_router.include_router(apikeys_router)
    app.include_router(api_router)

    # Provide a fake flask_app on state so _get_flask_app works.
    mock_flask_app = MagicMock()
    mock_flask_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
    mock_flask_app.app_context.return_value.__exit__ = MagicMock(return_value=False)
    app.state.flask_app = mock_flask_app

    client = TestClient(app, raise_server_exceptions=False)
    return app, client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_user():
    return _make_mock_user(user_id=1, username="admin", role_name="Administrator")


@pytest.fixture()
def app_client():
    """Return (app, client) tuple bound to the management routers."""
    return _build_app_and_client()


@pytest.fixture()
def client(app_client):
    """Return just the TestClient."""
    return app_client[1]


# ---------------------------------------------------------------------------
# Patch-target constants
# ---------------------------------------------------------------------------

# Auth (module-level function -- works for require_role closures)
_AUTH = "powerdnsadmin.api.deps.get_current_user"

# Models (canonical source modules -- deferred imports resolve here)
_USER_MODEL = "powerdnsadmin.models.user.User"
_ROLE_MODEL = "powerdnsadmin.models.role.Role"
_ACCOUNT_MODEL = "powerdnsadmin.models.account.Account"
_ACCOUNT_USER_MODEL = "powerdnsadmin.models.account.AccountUser"
_DOMAIN_MODEL = "powerdnsadmin.models.domain.Domain"
_DOMAIN_USER_MODEL = "powerdnsadmin.models.domain.DomainUser"
_HISTORY_MODEL = "powerdnsadmin.models.history.History"
_APIKEY_MODEL = "powerdnsadmin.models.api_key.ApiKey"
_DB_MODEL = "powerdnsadmin.models.base.db"

# Schemas (re-exported via powerdnsadmin.schemas.__init__)
_USER_SUMMARY_SCHEMA = "powerdnsadmin.schemas.UserSummary"
_USER_DETAILED_SCHEMA = "powerdnsadmin.schemas.UserDetailed"
_ACCOUNT_DETAIL_SCHEMA = "powerdnsadmin.schemas.AccountDetail"
_APIKEY_PLAIN_SCHEMA = "powerdnsadmin.schemas.ApiKeyPlain"
_APIKEY_DETAIL_SCHEMA = "powerdnsadmin.schemas.ApiKeyDetail"

# _get_json_body helpers on each route module (for request-body endpoints)
_USERS_GET_JSON = "powerdnsadmin.api.v1.users._get_json_body"
_ACCOUNTS_GET_JSON = "powerdnsadmin.api.v1.accounts._get_json_body"
_APIKEYS_GET_JSON = "powerdnsadmin.api.v1.apikeys._get_json_body"


# ===================================================================
# USER ENDPOINT TESTS
# ===================================================================


class TestListUsers:
    """GET /api/v1/pdnsadmin/users"""

    def test_list_users_as_admin(self, client, admin_user):
        mock_user_obj = _make_mock_user(user_id=10, username="alice", role_name="User")

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_USER_SUMMARY_SCHEMA) as MockSchema:
            MockUser.query.all.return_value = [mock_user_obj]
            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 10,
                "username": "alice",
                "firstname": "Alice",
                "lastname": "Smith",
                "email": "alice@example.com",
                "role": {"id": 2, "name": "User"},
            }

            resp = client.get("/api/v1/pdnsadmin/users")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["username"] == "alice"


class TestGetUser:
    """GET /api/v1/pdnsadmin/users/{username}"""

    def test_get_user_found(self, client, admin_user):
        target = _make_mock_user(user_id=5, username="bob", role_name="User")

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_USER_DETAILED_SCHEMA) as MockSchema:
            MockUser.query.filter.return_value.first.return_value = target
            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 5,
                "username": "bob",
                "firstname": None,
                "lastname": None,
                "email": None,
                "role": None,
                "accounts": [],
            }

            resp = client.get("/api/v1/pdnsadmin/users/bob")

        assert resp.status_code == 200
        assert resp.json()["username"] == "bob"

    def test_get_user_not_found(self, client, admin_user):
        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser:
            MockUser.query.filter.return_value.first.return_value = None

            resp = client.get("/api/v1/pdnsadmin/users/nonexistent")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestCreateUser:
    """POST /api/v1/pdnsadmin/users"""

    def test_create_user_success(self, client, admin_user):
        mock_role = MagicMock()
        mock_role.id = 3
        mock_role.name = "User"

        new_user_instance = MagicMock()
        new_user_instance.username = "newuser"
        new_user_instance.create_local_user.return_value = {"status": True}

        data = {"username": "newuser", "plain_text_password": "secret123"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL, return_value=new_user_instance), \
             patch(_HISTORY_MODEL), \
             patch(_USER_SUMMARY_SCHEMA) as MockSchema, \
             patch(_ROLE_MODEL) as MockRole, \
             patch(_USERS_GET_JSON, return_value=data):
            MockRole.query.filter.return_value.first.return_value = mock_role

            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 99,
                "username": "newuser",
                "firstname": None,
                "lastname": None,
                "email": None,
                "role": {"id": 3, "name": "User"},
            }

            resp = client.post(
                "/api/v1/pdnsadmin/users",
                content=json.dumps(data),
            )

        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser"

    def test_create_user_missing_username(self, client, admin_user):
        data = {"email": "test@example.com"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_USERS_GET_JSON, return_value=data):
            resp = client.post(
                "/api/v1/pdnsadmin/users",
                content=json.dumps(data),
            )

        assert resp.status_code == 400
        assert "username" in resp.json()["detail"].lower()


class TestUpdateUser:
    """PUT /api/v1/pdnsadmin/users/{user_id}"""

    def test_update_user_success(self, client, admin_user):
        target = _make_mock_user(user_id=5, username="bob", role_name="User")
        target.update_local_user.return_value = {"status": True}

        data = {"firstname": "Robert"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_HISTORY_MODEL), \
             patch(_USERS_GET_JSON, return_value=data):
            MockUser.query.get.return_value = target

            resp = client.put(
                "/api/v1/pdnsadmin/users/5",
                content=json.dumps(data),
            )

        assert resp.status_code == 204

    def test_update_user_not_found(self, client, admin_user):
        data = {"firstname": "Nobody"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_USERS_GET_JSON, return_value=data):
            MockUser.query.get.return_value = None

            resp = client.put(
                "/api/v1/pdnsadmin/users/999",
                content=json.dumps(data),
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_user_cannot_change_username(self, client, admin_user):
        target = _make_mock_user(user_id=5, username="bob", role_name="User")
        data = {"username": "different_name"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_USERS_GET_JSON, return_value=data):
            MockUser.query.get.return_value = target

            resp = client.put(
                "/api/v1/pdnsadmin/users/5",
                content=json.dumps(data),
            )

        assert resp.status_code == 400
        assert "cannot change username" in resp.json()["detail"].lower()


class TestDeleteUser:
    """DELETE /api/v1/pdnsadmin/users/{user_id}"""

    def test_delete_user_success(self, client, admin_user):
        target = _make_mock_user(user_id=5, username="bob", role_name="User")
        target.delete.return_value = True

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNT_USER_MODEL), \
             patch(_HISTORY_MODEL):
            MockUser.query.get.return_value = target
            MockAccount.query.join.return_value.join.return_value.filter.return_value.all.return_value = []

            resp = client.delete("/api/v1/pdnsadmin/users/5")

        assert resp.status_code == 204

    def test_delete_user_cannot_delete_self(self, client, admin_user):
        """Deleting yourself should return 500."""
        target = _make_mock_user(user_id=1, username="admin", role_name="Administrator")

        with patch(_AUTH, return_value=admin_user), \
             patch(_USER_MODEL) as MockUser, \
             patch(_ACCOUNT_MODEL), \
             patch(_ACCOUNT_USER_MODEL):
            MockUser.query.get.return_value = target

            resp = client.delete("/api/v1/pdnsadmin/users/1")

        assert resp.status_code == 500
        assert "cannot delete self" in resp.json()["detail"].lower()


# ===================================================================
# ACCOUNT ENDPOINT TESTS
# ===================================================================


class TestListAccounts:
    """GET /api/v1/pdnsadmin/accounts"""

    def test_list_accounts(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNT_DETAIL_SCHEMA) as MockSchema:
            MockAccount.query.all.return_value = [acct]
            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 1,
                "name": "acme",
                "description": "Test account",
                "contact": "contact@example.com",
                "mail": "mail@example.com",
                "domains": [],
                "apikeys": [],
            }

            resp = client.get("/api/v1/pdnsadmin/accounts")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "acme"


class TestGetAccount:
    """GET /api/v1/pdnsadmin/accounts/{account_name}"""

    def test_get_account_found(self, client, admin_user):
        acct = _make_mock_account(account_id=2, name="widgets")

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNT_DETAIL_SCHEMA) as MockSchema:
            MockAccount.query.filter.return_value.first.return_value = acct
            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 2,
                "name": "widgets",
                "description": "Test account",
                "contact": None,
                "mail": None,
                "domains": [],
                "apikeys": [],
            }

            resp = client.get("/api/v1/pdnsadmin/accounts/widgets")

        assert resp.status_code == 200
        assert resp.json()["name"] == "widgets"

    def test_get_account_not_found(self, client, admin_user):
        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount:
            MockAccount.query.filter.return_value.first.return_value = None

            resp = client.get("/api/v1/pdnsadmin/accounts/nonexistent")

        assert resp.status_code == 404


class TestCreateAccount:
    """POST /api/v1/pdnsadmin/accounts"""

    def test_create_account_success(self, client, admin_user):
        acct_instance = _make_mock_account(account_id=10, name="new-account")
        acct_instance.create_account.return_value = {"status": True}

        data = {"name": "new-account"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_HISTORY_MODEL), \
             patch(_ACCOUNT_DETAIL_SCHEMA) as MockSchema, \
             patch(_ACCOUNTS_GET_JSON, return_value=data):
            MockAccount.sanitize_name.return_value = "new-account"
            MockAccount.query.filter.return_value.all.return_value = []
            MockAccount.return_value = acct_instance

            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 10,
                "name": "new-account",
                "description": None,
                "contact": None,
                "mail": None,
                "domains": [],
                "apikeys": [],
            }

            resp = client.post(
                "/api/v1/pdnsadmin/accounts",
                content=json.dumps(data),
            )

        assert resp.status_code == 201
        assert resp.json()["name"] == "new-account"

    def test_create_account_missing_name(self, client, admin_user):
        data = {"description": "no name"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNTS_GET_JSON, return_value=data):
            resp = client.post(
                "/api/v1/pdnsadmin/accounts",
                content=json.dumps(data),
            )

        assert resp.status_code == 400
        assert "name" in resp.json()["detail"].lower()

    def test_create_account_duplicate_name(self, client, admin_user):
        existing = _make_mock_account(account_id=1, name="existing")
        data = {"name": "existing"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNTS_GET_JSON, return_value=data):
            MockAccount.sanitize_name.return_value = "existing"
            MockAccount.query.filter.return_value.all.return_value = [existing]

            resp = client.post(
                "/api/v1/pdnsadmin/accounts",
                content=json.dumps(data),
            )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()


class TestUpdateAccount:
    """PUT /api/v1/pdnsadmin/accounts/{account_id}"""

    def test_update_account_success(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")
        acct.update_account.return_value = {"status": True}

        data = {"description": "Updated desc"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_HISTORY_MODEL), \
             patch(_ACCOUNTS_GET_JSON, return_value=data):
            MockAccount.query.get.return_value = acct
            MockAccount.sanitize_name.return_value = "acme"

            resp = client.put(
                "/api/v1/pdnsadmin/accounts/1",
                content=json.dumps(data),
            )

        assert resp.status_code == 204

    def test_update_account_not_found(self, client, admin_user):
        data = {"description": "Nope"}

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNTS_GET_JSON, return_value=data):
            MockAccount.query.get.return_value = None

            resp = client.put(
                "/api/v1/pdnsadmin/accounts/999",
                content=json.dumps(data),
            )

        assert resp.status_code == 404


class TestDeleteAccount:
    """DELETE /api/v1/pdnsadmin/accounts/{account_id}"""

    def test_delete_account_success(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")
        acct.domains = []
        acct.delete_account.return_value = True

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_DOMAIN_MODEL), \
             patch(_HISTORY_MODEL):
            MockAccount.query.filter.return_value.all.return_value = [acct]

            resp = client.delete("/api/v1/pdnsadmin/accounts/1")

        assert resp.status_code == 204

    def test_delete_account_not_found(self, client, admin_user):
        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_DOMAIN_MODEL), \
             patch(_HISTORY_MODEL):
            MockAccount.query.filter.return_value.all.return_value = []

            resp = client.delete("/api/v1/pdnsadmin/accounts/999")

        assert resp.status_code == 404


class TestListAccountUsers:
    """GET /api/v1/pdnsadmin/accounts/{account_id}/users"""

    def test_list_account_users(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")
        member = _make_mock_user(user_id=10, username="member", role_name="User")

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNT_USER_MODEL), \
             patch(_USER_MODEL) as MockUser, \
             patch(_USER_SUMMARY_SCHEMA) as MockSchema:
            MockAccount.query.get.return_value = acct
            MockUser.query.join.return_value.filter.return_value.all.return_value = [member]
            MockSchema.model_validate.return_value.model_dump.return_value = {
                "id": 10,
                "username": "member",
                "firstname": None,
                "lastname": None,
                "email": None,
                "role": None,
            }

            resp = client.get("/api/v1/pdnsadmin/accounts/1/users")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "member"


class TestAddAccountUser:
    """PUT /api/v1/pdnsadmin/accounts/{account_id}/users/{user_id}"""

    def test_add_account_user_success(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")
        acct.add_user.return_value = True
        target = _make_mock_user(user_id=10, username="member", role_name="User")

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_USER_MODEL) as MockUser, \
             patch(_HISTORY_MODEL):
            MockAccount.query.get.return_value = acct
            MockUser.query.get.return_value = target

            resp = client.put("/api/v1/pdnsadmin/accounts/1/users/10")

        assert resp.status_code == 204


class TestRemoveAccountUser:
    """DELETE /api/v1/pdnsadmin/accounts/{account_id}/users/{user_id}"""

    def test_remove_account_user_success(self, client, admin_user):
        acct = _make_mock_account(account_id=1, name="acme")
        acct.remove_user.return_value = True
        target = _make_mock_user(user_id=10, username="member", role_name="User")

        with patch(_AUTH, return_value=admin_user), \
             patch(_ACCOUNT_MODEL) as MockAccount, \
             patch(_ACCOUNT_USER_MODEL), \
             patch(_USER_MODEL) as MockUser, \
             patch(_HISTORY_MODEL):
            MockAccount.query.get.return_value = acct
            MockUser.query.get.return_value = target
            MockUser.query.join.return_value.filter.return_value.all.return_value = [target]

            resp = client.delete("/api/v1/pdnsadmin/accounts/1/users/10")

        assert resp.status_code == 204


# ===================================================================
# API KEY ENDPOINT TESTS
#
# Apikey routes use Depends(get_current_user) directly, so the
# FastAPI dependency_overrides mechanism is required instead of
# patching the module-level function.
# ===================================================================


class TestCreateApiKey:
    """POST /api/v1/pdnsadmin/apikeys"""

    def test_create_apikey_success(self, app_client, admin_user):
        app, client = app_client
        app.dependency_overrides[_real_get_current_user] = lambda: admin_user

        mock_apikey = _make_mock_apikey(key_id=1, description="my key", role_name="Administrator")
        mock_apikey.plain_key = "plainkey123"

        data = {"role": "Administrator", "description": "my key"}

        try:
            with patch(_APIKEY_MODEL, return_value=mock_apikey), \
                 patch(_DOMAIN_MODEL), \
                 patch(_DOMAIN_USER_MODEL), \
                 patch(_ACCOUNT_MODEL), \
                 patch(_ACCOUNT_USER_MODEL), \
                 patch(_USER_MODEL), \
                 patch(_DB_MODEL), \
                 patch(_APIKEY_PLAIN_SCHEMA) as MockSchema, \
                 patch(_APIKEYS_GET_JSON, return_value=data):
                mock_apikey.create.return_value = None

                MockSchema.model_validate.return_value.model_dump.return_value = {
                    "id": 1,
                    "role": {"id": 1, "name": "Administrator"},
                    "domains": [],
                    "accounts": [],
                    "description": "my key",
                    "plain_key": "cGxhaW5rZXkxMjM=",
                }

                resp = client.post(
                    "/api/v1/pdnsadmin/apikeys",
                    content=json.dumps(data),
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        result = resp.json()
        assert result["description"] == "my key"
        assert "plain_key" in result

    def test_create_apikey_missing_role(self, app_client, admin_user):
        app, client = app_client
        app.dependency_overrides[_real_get_current_user] = lambda: admin_user

        data = {"description": "no role"}

        try:
            with patch(_APIKEY_MODEL), \
                 patch(_DOMAIN_MODEL), \
                 patch(_DOMAIN_USER_MODEL), \
                 patch(_ACCOUNT_MODEL), \
                 patch(_ACCOUNT_USER_MODEL), \
                 patch(_USER_MODEL), \
                 patch(_DB_MODEL), \
                 patch(_APIKEYS_GET_JSON, return_value=data):
                resp = client.post(
                    "/api/v1/pdnsadmin/apikeys",
                    content=json.dumps(data),
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert "role" in resp.json()["detail"].lower()


class TestListApiKeys:
    """GET /api/v1/pdnsadmin/apikeys"""

    def test_list_apikeys_as_admin(self, app_client, admin_user):
        app, client = app_client
        app.dependency_overrides[_real_get_current_user] = lambda: admin_user

        mock_key = _make_mock_apikey(key_id=1, description="key1")

        try:
            with patch(_APIKEY_MODEL) as MockApiKey, \
                 patch(_DOMAIN_MODEL), \
                 patch(_DOMAIN_USER_MODEL), \
                 patch(_ACCOUNT_MODEL), \
                 patch(_ACCOUNT_USER_MODEL), \
                 patch(_USER_MODEL), \
                 patch(_DB_MODEL), \
                 patch(_APIKEY_DETAIL_SCHEMA) as MockSchema:
                MockApiKey.query.all.return_value = [mock_key]
                MockSchema.model_validate.return_value.model_dump.return_value = {
                    "id": 1,
                    "role": {"id": 1, "name": "Administrator"},
                    "domains": [],
                    "accounts": [],
                    "description": "key1",
                    "key": None,
                }

                resp = client.get("/api/v1/pdnsadmin/apikeys")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 1


class TestDeleteApiKey:
    """DELETE /api/v1/pdnsadmin/apikeys/{apikey_id}"""

    def test_delete_apikey_success(self, app_client, admin_user):
        app, client = app_client
        app.dependency_overrides[_real_get_current_user] = lambda: admin_user

        mock_key = _make_mock_apikey(key_id=5)
        mock_key.delete.return_value = None

        try:
            with patch(_APIKEY_MODEL) as MockApiKey, \
                 patch(_DOMAIN_MODEL), \
                 patch(_DOMAIN_USER_MODEL), \
                 patch(_ACCOUNT_MODEL), \
                 patch(_ACCOUNT_USER_MODEL), \
                 patch(_USER_MODEL), \
                 patch(_DB_MODEL):
                MockApiKey.query.get.return_value = mock_key

                resp = client.delete("/api/v1/pdnsadmin/apikeys/5")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 204

    def test_delete_apikey_not_found(self, app_client, admin_user):
        app, client = app_client
        app.dependency_overrides[_real_get_current_user] = lambda: admin_user

        try:
            with patch(_APIKEY_MODEL) as MockApiKey, \
                 patch(_DOMAIN_MODEL), \
                 patch(_DOMAIN_USER_MODEL), \
                 patch(_ACCOUNT_MODEL), \
                 patch(_ACCOUNT_USER_MODEL), \
                 patch(_USER_MODEL), \
                 patch(_DB_MODEL):
                MockApiKey.query.get.return_value = None

                resp = client.delete("/api/v1/pdnsadmin/apikeys/999")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404
