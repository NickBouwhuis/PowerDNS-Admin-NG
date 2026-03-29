"""
API v2 settings endpoints — session-based settings management for the SPA.

Provides grouped settings for Basic, PDNS, Records, and Authentication.
All endpoints require Administrator or Operator role via session auth.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings-v2"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_authenticated_user(request: Request):
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="Session middleware not configured")
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.session.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _require_admin_or_operator(user):
    if user.role.name not in ["Administrator", "Operator"]:
        raise HTTPException(status_code=403, detail="Insufficient privileges")


# The basic settings displayed on the Basic Settings page
BASIC_SETTING_KEYS = [
    "account_name_extra_chars",
    "allow_user_create_domain",
    "allow_user_remove_domain",
    "allow_user_view_history",
    "auto_ptr",
    "bg_domain_updates",
    "custom_css",
    "default_domain_table_size",
    "default_record_table_size",
    "delete_sso_accounts",
    "custom_history_header",
    "deny_domain_override",
    "dnssec_admins_only",
    "enable_api_rr_history",
    "enforce_api_ttl",
    "fullscreen_layout",
    "gravatar_enabled",
    "login_ldap_first",
    "maintenance",
    "max_history_records",
    "otp_field_enabled",
    "otp_force",
    "pdns_api_timeout",
    "preserve_history",
    "pretty_ipv6_ptr",
    "record_helper",
    "record_quick_edit",
    "session_timeout",
    "site_name",
    "ttl_options",
    "verify_ssl_connections",
    "verify_user_email",
    "warn_session_timeout",
]

# PDNS connection settings
PDNS_SETTING_KEYS = [
    "pdns_api_url",
    "pdns_api_key",
    "pdns_version",
]

# Auth setting keys by provider
AUTH_SETTING_KEYS = {
    "local": [
        "local_db_enabled", "signup_enabled",
        "pwd_enforce_characters", "pwd_min_len", "pwd_min_lowercase",
        "pwd_min_uppercase", "pwd_min_digits", "pwd_min_special",
        "pwd_enforce_complexity", "pwd_min_complexity",
    ],
    "ldap": [
        "ldap_enabled", "ldap_type", "ldap_uri", "ldap_base_dn",
        "ldap_admin_username", "ldap_admin_password", "ldap_domain",
        "ldap_filter_basic", "ldap_filter_username", "ldap_filter_group",
        "ldap_filter_groupname", "ldap_sg_enabled", "ldap_admin_group",
        "ldap_operator_group", "ldap_user_group", "ldap_tls_verify",
        "autoprovisioning", "autoprovisioning_attribute", "urn_value", "purge",
    ],
    "google": [
        "google_oauth_enabled", "google_oauth_client_id",
        "google_oauth_client_secret", "google_oauth_scope",
        "google_base_url", "google_oauth_auto_configure",
        "google_oauth_metadata_url", "google_token_url",
        "google_authorize_url",
    ],
    "github": [
        "github_oauth_enabled", "github_oauth_key",
        "github_oauth_secret", "github_oauth_scope",
        "github_oauth_api_url", "github_oauth_auto_configure",
        "github_oauth_metadata_url", "github_oauth_token_url",
        "github_oauth_authorize_url",
    ],
    "azure": [
        "azure_oauth_enabled", "azure_oauth_key",
        "azure_oauth_secret", "azure_oauth_scope",
        "azure_oauth_api_url", "azure_oauth_auto_configure",
        "azure_oauth_metadata_url", "azure_oauth_token_url",
        "azure_oauth_authorize_url",
        "azure_sg_enabled", "azure_admin_group",
        "azure_operator_group", "azure_user_group",
        "azure_group_accounts_enabled", "azure_group_accounts_name",
        "azure_group_accounts_name_re", "azure_group_accounts_description",
        "azure_group_accounts_description_re",
    ],
    "oidc": [
        "oidc_oauth_enabled", "oidc_oauth_key",
        "oidc_oauth_secret", "oidc_oauth_scope",
        "oidc_oauth_api_url", "oidc_oauth_auto_configure",
        "oidc_oauth_metadata_url", "oidc_oauth_token_url",
        "oidc_oauth_authorize_url", "oidc_oauth_logout_url",
        "oidc_oauth_username", "oidc_oauth_email",
        "oidc_oauth_firstname", "oidc_oauth_last_name",
        "oidc_oauth_account_name_property",
        "oidc_oauth_account_description_property",
    ],
    "saml": [
        "saml_enabled", "saml_debug", "saml_metadata_url",
        "saml_metadata_cache_lifetime", "saml_idp_sso_binding",
        "saml_idp_entity_id", "saml_nameid_format",
        "saml_attribute_account", "saml_attribute_email",
        "saml_attribute_givenname", "saml_attribute_surname",
        "saml_attribute_name", "saml_attribute_username",
        "saml_attribute_admin", "saml_attribute_group",
        "saml_group_admin_name", "saml_group_operator_name",
        "saml_group_to_account_mapping",
        "saml_sp_entity_id", "saml_sp_contact_name",
        "saml_sp_contact_mail", "saml_sign_request",
        "saml_want_message_signed", "saml_logout",
        "saml_logout_url", "saml_assertion_encrypted",
        "saml_cert", "saml_key",
    ],
}


def _get_setting_value(setting_obj, key):
    """Get a single setting value, with type info."""
    from powerdnsadmin.lib.settings import AppSettings

    value = setting_obj.get(key)
    # Determine type
    setting_type = "string"
    if key in getattr(AppSettings, "types", {}):
        py_type = AppSettings.types[key]
        if py_type == bool:
            setting_type = "boolean"
        elif py_type == int:
            setting_type = "integer"
        elif py_type == dict:
            setting_type = "dict"
        elif py_type == list:
            setting_type = "list"

    # Coerce booleans from string
    if setting_type == "boolean" and isinstance(value, str):
        value = value.lower() in ("true", "1", "yes")

    return {"key": key, "value": value, "type": setting_type}


def _get_settings_dict(setting_obj, keys):
    """Get multiple settings as a list of {key, value, type} dicts."""
    return [_get_setting_value(setting_obj, k) for k in keys]


# ===================================================================
# BASIC SETTINGS
# ===================================================================

@router.get("/basic")
async def get_basic_settings(request: Request):
    """Get all basic settings."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    s = Setting()
    return _get_settings_dict(s, BASIC_SETTING_KEYS)


@router.put("/basic")
async def update_basic_settings(request: Request):
    """Update one or more basic settings. Body: {key: value, ...}"""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    body = await request.json()
    s = Setting()
    updated = []

    for key, value in body.items():
        if key not in BASIC_SETTING_KEYS:
            continue
        try:
            s.set(key, value)
            updated.append(key)
        except Exception as e:
            logger.error("Failed to update setting %s: %s", key, e)
            raise HTTPException(status_code=400, detail=f"Failed to update {key}: {e}")

    return {"status": "ok", "updated": updated}


@router.put("/basic/{key}/toggle")
async def toggle_basic_setting(key: str, request: Request):
    """Toggle a boolean setting."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    if key not in BASIC_SETTING_KEYS:
        raise HTTPException(status_code=404, detail="Setting not found")

    s = Setting()
    try:
        s.toggle(key)
        new_value = s.get(key)
        if isinstance(new_value, str):
            new_value = new_value.lower() in ("true", "1", "yes")
        return {"key": key, "value": new_value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===================================================================
# PDNS SETTINGS
# ===================================================================

@router.get("/pdns")
async def get_pdns_settings(request: Request):
    """Get PowerDNS connection settings."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    s = Setting()
    return _get_settings_dict(s, PDNS_SETTING_KEYS)


@router.put("/pdns")
async def update_pdns_settings(request: Request):
    """Update PowerDNS connection settings."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    body = await request.json()
    s = Setting()

    for key in PDNS_SETTING_KEYS:
        if key in body:
            # Validate API URL
            if key == "pdns_api_url":
                url = body[key].strip()
                if url and not url.startswith(("http://", "https://")):
                    raise HTTPException(
                        status_code=400,
                        detail="PDNS API URL must start with http:// or https://",
                    )
                body[key] = url.rstrip("/")

            s.set(key, body[key])

    return {"status": "ok", "message": "PDNS settings updated"}


@router.post("/pdns/test")
async def test_pdns_connection(request: Request):
    """Test the PowerDNS API connection."""
    from powerdnsadmin.services.pdns_client import PowerDNSClient

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    try:
        client = PowerDNSClient()
        info = client.get_config()
        version = client.get_server_version() if hasattr(client, "get_server_version") else None
        return {
            "status": "ok",
            "message": "Connection successful",
            "version": version,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Connection failed: {e}",
        }


# ===================================================================
# RECORD TYPE SETTINGS
# ===================================================================

@router.get("/records")
async def get_record_settings(request: Request):
    """Get allowed record types for forward and reverse zones."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    s = Setting()
    forward = s.get("forward_records_allow_edit")
    reverse = s.get("reverse_records_allow_edit")

    # Ensure they're dicts
    if isinstance(forward, str):
        import json
        try:
            forward = json.loads(forward)
        except (json.JSONDecodeError, TypeError):
            forward = {}
    if isinstance(reverse, str):
        import json
        try:
            reverse = json.loads(reverse)
        except (json.JSONDecodeError, TypeError):
            reverse = {}

    return {
        "forward": forward or {},
        "reverse": reverse or {},
    }


@router.put("/records")
async def update_record_settings(request: Request):
    """Update allowed record types for forward and reverse zones."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    body = await request.json()
    s = Setting()

    if "forward" in body:
        s.set("forward_records_allow_edit", body["forward"])
    if "reverse" in body:
        s.set("reverse_records_allow_edit", body["reverse"])

    return {"status": "ok", "message": "Record settings updated"}


# ===================================================================
# AUTHENTICATION SETTINGS
# ===================================================================

@router.get("/authentication")
async def get_auth_settings(request: Request):
    """Get all authentication settings grouped by provider."""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    s = Setting()
    result = {}
    for provider, keys in AUTH_SETTING_KEYS.items():
        result[provider] = {}
        for key in keys:
            value = s.get(key)
            # Coerce string booleans
            if isinstance(value, str) and value.lower() in ("true", "false"):
                value = value.lower() == "true"
            result[provider][key] = value

    return result


@router.put("/authentication")
async def update_auth_settings(request: Request):
    """Update authentication settings. Body: {key: value, ...}"""
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    body = await request.json()
    s = Setting()

    # Flatten all valid auth keys
    all_auth_keys = set()
    for keys in AUTH_SETTING_KEYS.values():
        all_auth_keys.update(keys)

    updated = []
    for key, value in body.items():
        if key not in all_auth_keys:
            continue
        try:
            s.set(key, value)
            updated.append(key)
        except Exception as e:
            logger.error("Failed to update auth setting %s: %s", key, e)
            raise HTTPException(status_code=400, detail=f"Failed to update {key}: {e}")

    return {"status": "ok", "updated": updated}
