"""Unit tests for auth services (local and LDAP).

Tests password hashing, credential validation, and LDAP interactions
with fully mocked dependencies -- no Flask app or database needed.
"""
import pytest
from unittest.mock import patch, MagicMock

import powerdnsadmin.services.auth.local as local_mod
import powerdnsadmin.services.auth.ldap_auth as ldap_mod

# ── Local auth: pure functions (no Flask app needed) ──────────────────

from powerdnsadmin.services.auth.local import hash_password, check_password


class TestHashPassword:
    def test_returns_bytes(self):
        result = hash_password("secret")
        assert isinstance(result, bytes)

    def test_returns_none_for_none_input(self):
        assert hash_password(None) is None

    def test_different_calls_produce_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts differ each time

    def test_hash_is_valid_bcrypt(self):
        h = hash_password("test123")
        assert h.startswith(b"$2b$") or h.startswith(b"$2a$")


class TestCheckPassword:
    def test_matching_password(self):
        hashed = hash_password("correct-horse")
        assert check_password("correct-horse", hashed.decode("utf-8")) is True

    def test_wrong_password(self):
        hashed = hash_password("correct-horse")
        assert check_password("wrong-horse", hashed.decode("utf-8")) is False

    def test_none_plain_text(self):
        hashed = hash_password("anything")
        assert check_password(None, hashed.decode("utf-8")) is False

    def test_none_hashed(self):
        assert check_password("anything", None) is False

    def test_both_none(self):
        assert check_password(None, None) is False


# ── LocalAuthService.validate (requires mocking Flask + DB) ──────────

class TestLocalAuthServiceValidate:
    """Tests for LocalAuthService.validate.

    We mock db.session.execute so no real database is needed, and
    patch current_app.logger to avoid Flask context errors.
    """

    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        mock_app = MagicMock()
        with patch.object(local_mod, "db") as mock_db, \
             patch.object(local_mod, "current_app", mock_app):
            self.mock_db = mock_db
            self.mock_logger = mock_app.logger
            self.service = local_mod.LocalAuthService()
            yield

    def _make_user(self, username="alice", plain_password="s3cret"):
        hashed = hash_password(plain_password).decode("utf-8")
        user = MagicMock()
        user.username = username
        user.password = hashed
        return user

    def _set_user_lookup(self, user):
        self.mock_db.session.execute.return_value \
            .scalar_one_or_none.return_value = user

    def test_successful_login(self):
        user = self._make_user(plain_password="good-pw")
        self._set_user_lookup(user)

        result = self.service.validate("alice", "good-pw", src_ip="127.0.0.1")
        assert result is True
        self.mock_logger.info.assert_called_once()

    def test_trust_user_skips_password_check(self):
        user = self._make_user(plain_password="irrelevant")
        self._set_user_lookup(user)

        result = self.service.validate("alice", "wrong-pw", trust_user=True)
        assert result is True

    def test_wrong_password(self):
        user = self._make_user(plain_password="correct")
        self._set_user_lookup(user)

        result = self.service.validate("alice", "incorrect")
        assert result is False
        self.mock_logger.error.assert_called_once()

    def test_nonexistent_user(self):
        self._set_user_lookup(None)

        result = self.service.validate("ghost", "any")
        assert result is False
        self.mock_logger.warning.assert_called_once()

    def test_user_with_no_password_and_no_trust(self):
        user = MagicMock()
        user.username = "alice"
        user.password = None
        self._set_user_lookup(user)

        result = self.service.validate("alice", "anything")
        assert result is False


# ── LDAP auth service ─────────────────────────────────────────────────

class TestLDAPEscapeFilterChars:
    def test_no_special_chars(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        assert LDAPAuthService.escape_filter_chars("hello") == "hello"

    def test_backslash(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        assert LDAPAuthService.escape_filter_chars("a\\b") == "a\\5cb"

    def test_asterisk(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        assert LDAPAuthService.escape_filter_chars("a*b") == "a\\2ab"

    def test_parentheses(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        assert LDAPAuthService.escape_filter_chars("(test)") == "\\28test\\29"

    def test_null_byte(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        assert LDAPAuthService.escape_filter_chars("a\x00b") == "a\\00b"

    def test_multiple_special_chars(self):
        from powerdnsadmin.services.auth.ldap_auth import LDAPAuthService
        result = LDAPAuthService.escape_filter_chars("CN=admin\\,(Users)")
        assert result == "CN=admin\\5c,\\28Users\\29"


class TestLDAPBind:

    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        mock_ldap = MagicMock()
        mock_app = MagicMock()

        # Provide constants the code references
        mock_ldap.OPT_X_TLS_REQUIRE_CERT = 0x6006
        mock_ldap.OPT_X_TLS_DEMAND = 0x02
        mock_ldap.OPT_X_TLS_NEVER = 0x00
        mock_ldap.OPT_REFERRALS = 0x0008
        mock_ldap.OPT_OFF = 0x00
        mock_ldap.OPT_PROTOCOL_VERSION = 0x0011
        mock_ldap.OPT_DEBUG_LEVEL = 0x5001
        mock_ldap.VERSION3 = 3
        mock_ldap.LDAPError = Exception

        self.mock_conn = MagicMock()
        mock_ldap.initialize.return_value = self.mock_conn

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.side_effect = lambda k: {
            'ldap_tls_verify': False,
            'ldap_uri': 'ldap://ldap.test:389',
        }.get(k)

        with patch.object(ldap_mod, "ldap", mock_ldap), \
             patch.object(ldap_mod, "current_app", mock_app), \
             patch.object(ldap_mod, "Setting", return_value=mock_setting_instance):
            self.mock_ldap = mock_ldap
            self.service = ldap_mod.LDAPAuthService()
            yield

    def test_bind_success(self):
        self.mock_conn.simple_bind_s.return_value = None
        assert self.service.bind("cn=admin,dc=test", "secret") is True
        self.mock_conn.simple_bind_s.assert_called_once_with(
            "cn=admin,dc=test", "secret")

    def test_bind_failure(self):
        self.mock_conn.simple_bind_s.side_effect = Exception("Bad creds")
        assert self.service.bind("cn=admin,dc=test", "wrong") is False


class TestLDAPValidate:

    LDAP_SETTINGS = {
        'ldap_type': 'ldap',
        'ldap_uri': 'ldap://ldap.test:389',
        'ldap_base_dn': 'dc=example,dc=com',
        'ldap_filter_basic': '(objectClass=inetOrgPerson)',
        'ldap_filter_username': 'uid',
        'ldap_filter_group': '(objectClass=posixGroup)',
        'ldap_filter_groupname': 'memberUid',
        'ldap_admin_group': None,
        'ldap_operator_group': None,
        'ldap_user_group': None,
        'ldap_sg_enabled': False,
        'ldap_domain': 'example.com',
        'ldap_admin_username': 'cn=admin,dc=example,dc=com',
        'ldap_admin_password': 'admin-secret',
        'ldap_tls_verify': False,
    }

    LDAP_USER_RESULT = [
        [(
            'uid=alice,ou=people,dc=example,dc=com',
            {
                'givenName': [b'Alice'],
                'sn': [b'Smith'],
                'mail': [b'alice@example.com'],
            }
        )]
    ]

    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        mock_ldap = MagicMock()
        mock_app = MagicMock()
        mock_db = MagicMock()

        mock_ldap.OPT_X_TLS_REQUIRE_CERT = 0x6006
        mock_ldap.OPT_X_TLS_DEMAND = 0x02
        mock_ldap.OPT_X_TLS_NEVER = 0x00
        mock_ldap.OPT_REFERRALS = 0x0008
        mock_ldap.OPT_OFF = 0x00
        mock_ldap.OPT_PROTOCOL_VERSION = 0x0011
        mock_ldap.OPT_DEBUG_LEVEL = 0x5001
        mock_ldap.VERSION3 = 3
        mock_ldap.SCOPE_SUBTREE = 2
        mock_ldap.RES_SEARCH_ENTRY = 100
        mock_ldap.LDAPError = Exception

        mock_ldap.filter = MagicMock()
        mock_ldap.filter.escape_filter_chars = lambda s: s

        self.mock_conn = MagicMock()
        mock_ldap.initialize.return_value = self.mock_conn

        mock_setting_instance = MagicMock()
        mock_setting_instance.get.side_effect = \
            lambda k: self.LDAP_SETTINGS.get(k)

        with patch.object(ldap_mod, "ldap", mock_ldap), \
             patch.object(ldap_mod, "current_app", mock_app), \
             patch.object(ldap_mod, "db", mock_db), \
             patch.object(ldap_mod, "Setting", return_value=mock_setting_instance):
            self.mock_ldap = mock_ldap
            self.mock_db = mock_db
            self.mock_logger = mock_app.logger
            self.service = ldap_mod.LDAPAuthService()
            yield

    def _setup_search_returns(self, user_result):
        self.mock_conn.search.return_value = 1
        if user_result:
            self.mock_conn.result.side_effect = [
                (self.mock_ldap.RES_SEARCH_ENTRY, user_result[0]),
                (None, []),
            ]
        else:
            self.mock_conn.result.side_effect = [(None, [])]

    def _setup_user_not_in_db(self):
        self.mock_db.session.execute.return_value \
            .scalar_one_or_none.return_value = None

    def _setup_user_in_db(self):
        mock_user = MagicMock()
        self.mock_db.session.execute.return_value \
            .scalar_one_or_none.return_value = mock_user
        return mock_user

    def test_validate_success_openldap(self):
        self._setup_search_returns(self.LDAP_USER_RESULT)
        self.mock_conn.simple_bind_s.return_value = None
        self._setup_user_not_in_db()

        with patch.object(self.service, '_create_ldap_user'):
            success, role = self.service.validate(
                "alice", "secret", src_ip="10.0.0.1")

        assert success is True
        assert role == 'User'

    def test_validate_success_existing_user(self):
        self._setup_search_returns(self.LDAP_USER_RESULT)
        self.mock_conn.simple_bind_s.return_value = None
        self._setup_user_in_db()

        success, role = self.service.validate("alice", "secret")
        assert success is True
        assert role == 'User'

    def test_validate_trust_user_skips_bind(self):
        self._setup_search_returns(self.LDAP_USER_RESULT)
        self._setup_user_in_db()

        success, role = self.service.validate(
            "alice", "ignored", trust_user=True)
        assert success is True
        assert role == 'User'

    def test_validate_user_not_found_in_ldap(self):
        self._setup_search_returns(None)
        self.mock_conn.simple_bind_s.return_value = None

        success, role = self.service.validate("ghost", "any")
        assert success is False
        assert role is None

    def test_validate_wrong_password_openldap(self):
        self._setup_search_returns(self.LDAP_USER_RESULT)
        self.mock_conn.simple_bind_s.side_effect = [
            None,                                    # admin bind for search
            Exception("Invalid credentials"),        # user bind
        ]

        success, role = self.service.validate("alice", "wrong")
        assert success is False
        assert role is None

    def test_validate_wrong_password_ad(self):
        original_get = self.service._get

        def ad_get(key):
            if key == 'ldap_type':
                return 'ad'
            return original_get(key)
        self.service._get = ad_get

        self.mock_conn.simple_bind_s.side_effect = Exception("Bad creds")

        success, role = self.service.validate("alice", "wrong")
        assert success is False
        assert role is None

    def test_validate_search_returns_empty_list(self):
        self._setup_search_returns([])
        self.mock_conn.simple_bind_s.return_value = None

        success, role = self.service.validate("alice", "secret")
        assert success is False
        assert role is None
