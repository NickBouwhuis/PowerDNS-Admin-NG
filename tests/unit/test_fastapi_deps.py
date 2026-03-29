"""Unit tests for FastAPI authentication dependencies.

Tests powerdnsadmin/api/deps.py -- all auth/authz dependency functions
used by FastAPI route handlers. Uses unittest.mock throughout to avoid
any SQLAlchemy or external service dependencies.

Because deps.py uses local (deferred) imports inside function bodies
(e.g. ``from powerdnsadmin.models.user import User``), we must patch
at the *source* module path rather than on the deps module itself.
"""
import base64
import pytest
from unittest.mock import MagicMock, Mock, patch

from fastapi import HTTPException

from powerdnsadmin.api import deps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(client_host="127.0.0.1", path_params=None):
    """Build a mock FastAPI Request with the attributes deps.py reads."""
    request = MagicMock()
    request.client.host = client_host
    request.path_params = path_params or {}
    return request


def _basic_auth_header(username, password):
    """Return a ``Basic <b64>`` Authorization header value."""
    raw = f"{username}:{password}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


def _b64(value):
    """Base64-encode a plain string."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


# Shorthand patch targets -- these are the *source* modules where the
# deferred imports resolve the names.
_USER = "powerdnsadmin.models.user.User"
_SETTING = "powerdnsadmin.models.setting.Setting"
_APIKEY = "powerdnsadmin.models.api_key.ApiKey"
_DB = "powerdnsadmin.models.base.db"
_SELECT = "powerdnsadmin.api.deps.select"  # module-level import on deps


# ===========================================================================
# get_current_user
# ===========================================================================

class TestGetCurrentUser:
    """Tests for get_current_user (HTTP Basic auth dependency)."""

    def test_missing_authorization_header_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=None)
        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()

    def test_empty_authorization_header_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization="")
        assert exc_info.value.status_code == 401

    def test_non_basic_scheme_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization="Bearer some-token")
        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower() or "invalid" in exc_info.value.detail.lower()

    def test_invalid_base64_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization="Basic !!!not-base64!!!")
        assert exc_info.value.status_code == 401
        assert "base64" in exc_info.value.detail.lower()

    def test_no_colon_in_decoded_credentials_raises_401(self):
        """Credentials without a colon separator should fail."""
        no_colon = base64.b64encode(b"usernameonly").decode("utf-8")
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=f"Basic {no_colon}")
        assert exc_info.value.status_code == 401
        assert "format" in exc_info.value.detail.lower()

    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_user_validation_fails_raises_401(self, MockUser, MockSetting, mock_db):
        """is_validate returns False -> 401."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = False
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        request = _make_request()

        header = _basic_auth_header("admin", "wrongpass")

        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=header)
        assert exc_info.value.status_code == 401
        assert "invalid credentials" in exc_info.value.detail.lower()

    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_email_not_verified_raises_401(self, MockUser, MockSetting, mock_db):
        """verify_user_email enabled + not confirmed -> 401."""
        mock_user = MagicMock()
        mock_user.email = "admin@example.com"
        mock_user.confirmed = False
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = True  # verify_user_email = True
        MockSetting.return_value = mock_setting_instance

        request = _make_request()

        header = _basic_auth_header("admin", "secret")

        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=header)
        assert exc_info.value.status_code == 401
        assert "email" in exc_info.value.detail.lower()

    @patch(_SELECT)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_valid_credentials_returns_user(self, MockUser, MockSetting, mock_db, mock_select):
        """Happy path: valid basic auth credentials return the User from DB."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = True
        mock_user.email = None  # skip email verification
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        authenticated_user = MagicMock(name="authenticated_user")
        authenticated_user.username = "admin"
        mock_db.session.execute.return_value.scalar_one_or_none.return_value = authenticated_user

        request = _make_request()

        header = _basic_auth_header("admin", "password123")

        result = deps.get_current_user(request, authorization=header, auth_method="LOCAL")
        assert result is authenticated_user
        mock_user.is_validate.assert_called_once()
        # Verify LOCAL method was used
        call_kwargs = mock_user.is_validate.call_args
        assert call_kwargs[1]["method"] == "LOCAL"

    @patch(_SELECT)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_ldap_auth_method(self, MockUser, MockSetting, mock_db, mock_select):
        """auth_method != LOCAL -> method='LDAP' is passed to is_validate."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = True
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        authenticated_user = MagicMock()
        mock_db.session.execute.return_value.scalar_one_or_none.return_value = authenticated_user

        request = _make_request()

        header = _basic_auth_header("ldapuser", "ldappass")

        result = deps.get_current_user(request, authorization=header, auth_method="LDAP")
        assert result is authenticated_user
        call_kwargs = mock_user.is_validate.call_args
        assert call_kwargs[1]["method"] == "LDAP"

    @patch(_SELECT)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_user_not_found_in_db_raises_401(self, MockUser, MockSetting, mock_db, mock_select):
        """is_validate passes but user not in DB -> 401."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = True
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        mock_db.session.execute.return_value.scalar_one_or_none.return_value = None

        request = _make_request()

        header = _basic_auth_header("ghost", "pass")

        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=header)
        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()

    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_is_validate_raises_exception_returns_401(self, MockUser, MockSetting, mock_db):
        """Unexpected exception during is_validate -> 401 'Authentication failed'."""
        mock_user = MagicMock()
        mock_user.is_validate.side_effect = RuntimeError("LDAP unreachable")
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        request = _make_request()

        header = _basic_auth_header("admin", "pass")

        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user(request, authorization=header)
        assert exc_info.value.status_code == 401
        assert "authentication failed" in exc_info.value.detail.lower()
        # Session must be rolled back to prevent poisoning the thread-local
        mock_db.session.rollback.assert_called_once()

    @patch(_SELECT)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_password_with_colons(self, MockUser, MockSetting, mock_db, mock_select):
        """Passwords may contain colons; only the first colon is the split."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = True
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        authenticated_user = MagicMock()
        mock_db.session.execute.return_value.scalar_one_or_none.return_value = authenticated_user

        request = _make_request()

        header = _basic_auth_header("admin", "pass:with:colons")

        result = deps.get_current_user(request, authorization=header)
        assert result is authenticated_user
        # Verify the User was constructed with the full password including colons
        call_kwargs = MockUser.call_args
        assert call_kwargs[1]["plain_text_password"] == "pass:with:colons"

    @patch(_SELECT)
    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_client_host_passed_to_is_validate(self, MockUser, MockSetting, mock_db, mock_select):
        """The client IP address is forwarded to is_validate."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = True
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        authenticated_user = MagicMock()
        mock_db.session.execute.return_value.scalar_one_or_none.return_value = authenticated_user

        request = _make_request(client_host="10.0.0.42")

        header = _basic_auth_header("admin", "pass")
        deps.get_current_user(request, authorization=header)

        call_kwargs = mock_user.is_validate.call_args
        assert call_kwargs[1]["src_ip"] == "10.0.0.42"

    @patch(_DB)
    @patch(_SETTING)
    @patch(_USER)
    def test_no_client_uses_empty_string_for_src_ip(self, MockUser, MockSetting, mock_db):
        """When request.client is None, src_ip should be empty string."""
        mock_user = MagicMock()
        mock_user.is_validate.return_value = False
        mock_user.email = None
        MockUser.return_value = mock_user

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.return_value = False
        MockSetting.return_value = mock_setting_instance

        request = _make_request()
        request.client = None

        header = _basic_auth_header("admin", "pass")

        with pytest.raises(HTTPException):
            deps.get_current_user(request, authorization=header)

        call_kwargs = mock_user.is_validate.call_args
        assert call_kwargs[1]["src_ip"] == ""


# ===========================================================================
# get_current_apikey
# ===========================================================================

class TestGetCurrentApikey:
    """Tests for get_current_apikey (X-API-KEY header dependency)."""

    def test_missing_x_api_key_header_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_apikey(request, x_api_key=None)
        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()

    def test_empty_x_api_key_header_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_apikey(request, x_api_key="")
        assert exc_info.value.status_code == 401

    def test_invalid_base64_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_apikey(request, x_api_key="!!!not-base64!!!")
        assert exc_info.value.status_code == 401
        assert "base64" in exc_info.value.detail.lower()

    @patch(_DB)
    @patch(_APIKEY)
    def test_apikey_validation_fails_raises_401(self, MockApiKey, mock_db):
        """is_validate raises an exception -> 401 and session is rolled back."""
        mock_apikey = MagicMock()
        mock_apikey.is_validate.side_effect = Exception("DB error")
        MockApiKey.return_value = mock_apikey

        request = _make_request()

        encoded_key = _b64("my-api-key-value")

        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_apikey(request, x_api_key=encoded_key)
        assert exc_info.value.status_code == 401
        assert "invalid api key" in exc_info.value.detail.lower()
        # Session must be rolled back to prevent poisoning the thread-local
        mock_db.session.rollback.assert_called_once()

    @patch(_APIKEY)
    def test_valid_apikey_returns_validated_object(self, MockApiKey):
        """Happy path: valid API key is decoded, validated, and returned."""
        validated_apikey = MagicMock(name="validated_apikey")
        mock_apikey = MagicMock()
        mock_apikey.is_validate.return_value = validated_apikey
        MockApiKey.return_value = mock_apikey

        request = _make_request()

        encoded_key = _b64("my-secret-api-key")

        result = deps.get_current_apikey(request, x_api_key=encoded_key)
        assert result is validated_apikey
        mock_apikey.is_validate.assert_called_once_with(
            method="LOCAL",
            src_ip="127.0.0.1",
        )

    @patch(_APIKEY)
    def test_apikey_constructed_with_correct_values(self, MockApiKey):
        """Verify the ApiKey is constructed with the decoded key value."""
        validated_apikey = MagicMock()
        mock_apikey = MagicMock()
        mock_apikey.is_validate.return_value = validated_apikey
        MockApiKey.return_value = mock_apikey

        request = _make_request()

        encoded_key = _b64("the-actual-key")
        deps.get_current_apikey(request, x_api_key=encoded_key)

        MockApiKey.assert_called_once_with(key="the-actual-key")
        assert mock_apikey.plain_text_password == "the-actual-key"

    @patch(_APIKEY)
    def test_apikey_client_ip_forwarded(self, MockApiKey):
        """Client IP is passed to is_validate."""
        validated_apikey = MagicMock()
        mock_apikey = MagicMock()
        mock_apikey.is_validate.return_value = validated_apikey
        MockApiKey.return_value = mock_apikey

        request = _make_request(client_host="192.168.1.100")

        encoded_key = _b64("key-value")
        deps.get_current_apikey(request, x_api_key=encoded_key)

        mock_apikey.is_validate.assert_called_once_with(
            method="LOCAL",
            src_ip="192.168.1.100",
        )


# ===========================================================================
# get_current_user_or_apikey
# ===========================================================================

class TestGetCurrentUserOrApikey:
    """Tests for get_current_user_or_apikey (dual-auth dependency)."""

    @patch.object(deps, "get_current_apikey")
    def test_with_x_api_key_delegates_to_get_current_apikey(self, mock_get_apikey):
        """When X-API-KEY header is present, delegates to get_current_apikey."""
        expected = MagicMock(name="apikey_result")
        mock_get_apikey.return_value = expected

        request = _make_request()
        result = deps.get_current_user_or_apikey(
            request,
            authorization="Basic dGVzdDp0ZXN0",
            x_api_key="some-encoded-key",
            auth_method="LOCAL",
        )
        assert result is expected
        mock_get_apikey.assert_called_once_with(request, "some-encoded-key")

    @patch.object(deps, "get_current_user")
    def test_without_x_api_key_delegates_to_get_current_user(self, mock_get_user):
        """When X-API-KEY header is absent, delegates to get_current_user."""
        expected = MagicMock(name="user_result")
        mock_get_user.return_value = expected

        request = _make_request()
        result = deps.get_current_user_or_apikey(
            request,
            authorization="Basic dGVzdDp0ZXN0",
            x_api_key=None,
            auth_method="LOCAL",
        )
        assert result is expected
        mock_get_user.assert_called_once_with(request, "Basic dGVzdDp0ZXN0", "LOCAL")

    @patch.object(deps, "get_current_user")
    def test_empty_x_api_key_delegates_to_get_current_user(self, mock_get_user):
        """Empty string X-API-KEY is falsy, so should delegate to user auth."""
        expected = MagicMock(name="user_result")
        mock_get_user.return_value = expected

        request = _make_request()
        result = deps.get_current_user_or_apikey(
            request,
            authorization="Basic dGVzdDp0ZXN0",
            x_api_key="",
            auth_method="LDAP",
        )
        assert result is expected
        mock_get_user.assert_called_once_with(request, "Basic dGVzdDp0ZXN0", "LDAP")

    @patch.object(deps, "get_current_apikey")
    def test_x_api_key_error_propagates(self, mock_get_apikey):
        """HTTPException from get_current_apikey is not caught."""
        mock_get_apikey.side_effect = HTTPException(status_code=401, detail="Invalid API key")

        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            deps.get_current_user_or_apikey(
                request,
                authorization=None,
                x_api_key="some-key",
                auth_method="LOCAL",
            )
        assert exc_info.value.status_code == 401


# ===========================================================================
# require_role
# ===========================================================================

class TestRequireRole:
    """Tests for the require_role() factory and its returned dependency."""

    @patch.object(deps, "get_current_user")
    def test_user_with_matching_role_returns_user(self, mock_get_user):
        """User whose role matches one of the required roles is allowed."""
        mock_user = MagicMock()
        mock_user.role.name = "Administrator"
        mock_user.username = "admin"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", "Operator")

        request = _make_request()
        result = dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert result is mock_user

    @patch.object(deps, "get_current_user")
    def test_user_with_non_matching_role_raises_401(self, mock_get_user):
        """User whose role doesn't match any required role gets 401."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.username = "regular"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", "Operator")

        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401
        assert "privileges" in exc_info.value.detail.lower()
        assert "regular" in exc_info.value.detail
        assert "User" in exc_info.value.detail

    @patch.object(deps, "get_current_user")
    def test_no_roles_specified_defaults_to_admin_and_operator(self, mock_get_user):
        """When no roles are given, defaults to ('Administrator', 'Operator')."""
        mock_user = MagicMock()
        mock_user.role.name = "Operator"
        mock_user.username = "ops"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role()

        request = _make_request()
        result = dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert result is mock_user

    @patch.object(deps, "get_current_user")
    def test_no_roles_specified_rejects_non_default(self, mock_get_user):
        """With default roles, a 'User' role is rejected."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.username = "somebody"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role()

        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_user")
    def test_allow_self_with_matching_user_id(self, mock_get_user):
        """allow_self=True allows access when user_id in path matches user.id."""
        mock_user = MagicMock()
        mock_user.role.name = "User"  # not in required roles
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={"user_id": "42"})
        result = dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert result is mock_user

    @patch.object(deps, "get_current_user")
    def test_allow_self_with_matching_username(self, mock_get_user):
        """allow_self=True allows access when username in path matches user.username."""
        mock_user = MagicMock()
        mock_user.role.name = "User"  # not in required roles
        mock_user.id = 99
        mock_user.username = "jdoe"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={"username": "jdoe"})
        result = dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert result is mock_user

    @patch.object(deps, "get_current_user")
    def test_allow_self_with_non_matching_user_id_raises_401(self, mock_get_user):
        """allow_self=True but user_id doesn't match -> 401."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={"user_id": "99"})
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_user")
    def test_allow_self_with_non_matching_username_raises_401(self, mock_get_user):
        """allow_self=True but username doesn't match -> 401."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={"username": "otheruser"})
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_user")
    def test_allow_self_no_path_params_raises_401(self, mock_get_user):
        """allow_self=True but no user_id or username in path -> 401."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={})
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_user")
    def test_allow_self_invalid_user_id_in_path_raises_401(self, mock_get_user):
        """allow_self=True with non-numeric user_id in path -> 401."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        request = _make_request(path_params={"user_id": "not-a-number"})
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_user")
    def test_role_match_takes_precedence_over_allow_self(self, mock_get_user):
        """If user role matches, return user even without allow_self match."""
        mock_user = MagicMock()
        mock_user.role.name = "Administrator"
        mock_user.id = 1
        mock_user.username = "admin"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=True)

        # Path params don't match user, but role does
        request = _make_request(path_params={"user_id": "999"})
        result = dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert result is mock_user

    @patch.object(deps, "get_current_user")
    def test_allow_self_false_ignores_path_params(self, mock_get_user):
        """Without allow_self, matching path params don't help."""
        mock_user = MagicMock()
        mock_user.role.name = "User"
        mock_user.id = 42
        mock_user.username = "selfuser"
        mock_get_user.return_value = mock_user

        dependency = deps.require_role("Administrator", allow_self=False)

        request = _make_request(path_params={"user_id": "42"})
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, authorization="Basic dGVzdDp0ZXN0", auth_method="LOCAL")
        assert exc_info.value.status_code == 401


# ===========================================================================
# require_apikey_role
# ===========================================================================

class TestRequireApikeyRole:
    """Tests for the require_apikey_role() factory and its returned dependency."""

    @patch.object(deps, "get_current_apikey")
    def test_apikey_with_matching_role_returns_apikey(self, mock_get_apikey):
        """API key whose role matches one of the required roles is allowed."""
        mock_apikey = MagicMock()
        mock_apikey.role.name = "Administrator"
        mock_get_apikey.return_value = mock_apikey

        request = _make_request()

        dependency = deps.require_apikey_role("Administrator", "Operator")
        result = dependency(request, x_api_key="some-key")
        assert result is mock_apikey

    @patch.object(deps, "get_current_apikey")
    def test_apikey_with_non_matching_role_raises_401(self, mock_get_apikey):
        """API key whose role doesn't match any required role gets 401."""
        mock_apikey = MagicMock()
        mock_apikey.role.name = "User"
        mock_get_apikey.return_value = mock_apikey

        request = _make_request()

        dependency = deps.require_apikey_role("Administrator", "Operator")
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, x_api_key="some-key")
        assert exc_info.value.status_code == 401
        assert "privileges" in exc_info.value.detail.lower()

    @patch.object(deps, "get_current_apikey")
    def test_no_roles_specified_defaults_to_admin_and_operator(self, mock_get_apikey):
        """When no roles are given, defaults to ('Administrator', 'Operator')."""
        mock_apikey = MagicMock()
        mock_apikey.role.name = "Operator"
        mock_get_apikey.return_value = mock_apikey

        request = _make_request()

        dependency = deps.require_apikey_role()
        result = dependency(request, x_api_key="some-key")
        assert result is mock_apikey

    @patch.object(deps, "get_current_apikey")
    def test_no_roles_specified_rejects_non_default(self, mock_get_apikey):
        """With default roles, a 'User' role API key is rejected."""
        mock_apikey = MagicMock()
        mock_apikey.role.name = "User"
        mock_get_apikey.return_value = mock_apikey

        request = _make_request()

        dependency = deps.require_apikey_role()
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, x_api_key="some-key")
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_apikey")
    def test_apikey_auth_error_propagates(self, mock_get_apikey):
        """If get_current_apikey raises 401, it propagates through."""
        mock_get_apikey.side_effect = HTTPException(
            status_code=401, detail="X-API-KEY header missing"
        )

        request = _make_request()
        dependency = deps.require_apikey_role("Administrator")
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, x_api_key=None)
        assert exc_info.value.status_code == 401

    @patch.object(deps, "get_current_apikey")
    def test_single_role_check(self, mock_get_apikey):
        """Single role argument works correctly."""
        mock_apikey = MagicMock()
        mock_apikey.role.name = "Administrator"
        mock_get_apikey.return_value = mock_apikey

        request = _make_request()

        # Only "Administrator" should pass
        dependency = deps.require_apikey_role("Administrator")
        result = dependency(request, x_api_key="some-key")
        assert result is mock_apikey

        # "Operator" should not pass the single-role check
        mock_apikey.role.name = "Operator"
        with pytest.raises(HTTPException) as exc_info:
            dependency(request, x_api_key="some-key")
        assert exc_info.value.status_code == 401


# ===========================================================================
# db_session_cleanup
# ===========================================================================

class TestDbSessionCleanup:
    """Tests for the db_session_cleanup yield dependency."""

    @patch(_DB)
    def test_session_removed_after_normal_request(self, mock_db):
        """Session is removed after a successful request."""
        gen = deps.db_session_cleanup()
        next(gen)  # enter the dependency
        with pytest.raises(StopIteration):
            next(gen)  # exit (finally block runs)
        mock_db.session.remove.assert_called_once()

    @patch(_DB)
    def test_session_rolled_back_and_removed_on_exception(self, mock_db):
        """Session is rolled back and removed when an exception occurs."""
        gen = deps.db_session_cleanup()
        next(gen)  # enter the dependency
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("DB failure"))
        mock_db.session.rollback.assert_called_once()
        mock_db.session.remove.assert_called_once()
