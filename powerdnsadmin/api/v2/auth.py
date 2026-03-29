"""
API v2 authentication endpoints — session-based auth for the SPA.

Reuses the existing server-side session middleware and auth services.
All endpoints return JSON (no redirects, no HTML templates).

Routes:
    POST /api/v2/auth/login           — authenticate with username/password
    POST /api/v2/auth/logout          — clear session
    GET  /api/v2/auth/me              — current user info + role + settings
    GET  /api/v2/auth/settings        — public auth settings (enabled providers)
"""
import json
import logging
import traceback

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from powerdnsadmin.core.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-v2"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    otp_token: str | None = None
    auth_method: str = "LOCAL"  # "LOCAL" or "LDAP"


class UserResponse(BaseModel):
    id: int
    username: str
    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    role: str
    otp_enabled: bool = False

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    status: str  # "ok", "otp_required", "error"
    message: str | None = None
    user: UserResponse | None = None


class AuthSettingsResponse(BaseModel):
    local_db_enabled: bool = True
    ldap_enabled: bool = False
    signup_enabled: bool = False
    google_oauth_enabled: bool = False
    github_oauth_enabled: bool = False
    azure_oauth_enabled: bool = False
    oidc_oauth_enabled: bool = False
    saml_enabled: bool = False
    otp_field_enabled: bool = False
    verify_user_email: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session(request: Request) -> dict:
    """Get session dict from request, raising 500 if middleware missing."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="Session middleware not configured")
    return session


def _user_to_response(user) -> UserResponse:
    """Convert a User model instance to UserResponse."""
    return UserResponse(
        id=user.id,
        username=user.username,
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        role=user.role.name,
        otp_enabled=bool(user.otp_secret),
    )


def _signin_history(request: Request, username: str, authenticator: str, success: bool):
    """Record a sign-in attempt in the history table."""
    from powerdnsadmin.models.history import History

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        request_ip = forwarded.split(",")[0].strip()
    else:
        request_ip = request.client.host if request.client else "unknown"

    if success:
        logger.info("User %s authenticated successfully via %s from %s",
                     username, authenticator, request_ip)
    else:
        logger.warning("User %s failed to authenticate via %s from %s",
                        username, authenticator, request_ip)

    History(
        msg="User {} authentication {}".format(
            username, "succeeded" if success else "failed"),
        detail=json.dumps({
            "username": username,
            "authenticator": authenticator,
            "ip_address": request_ip,
            "success": 1 if success else 0,
        }),
        created_by="System",
    ).add()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    """Authenticate user with username/password, optionally with OTP.

    Returns user info on success. If OTP is required but not provided,
    returns status="otp_required" so the SPA can show the OTP field.
    """
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.user import User

    session = _get_session(request)

    # Check if local auth is disabled
    if body.auth_method == "LOCAL" and not Setting().get("local_db_enabled"):
        raise HTTPException(status_code=400, detail="Local authentication is disabled")

    # Create a transient User for validation
    user = User(
        username=body.username,
        password=body.password,
        plain_text_password=body.password,
    )

    # Check email verification
    try:
        if Setting().get("verify_user_email") and user.email and not user.confirmed:
            raise HTTPException(
                status_code=403,
                detail="Please confirm your email address first",
            )

        client_ip = request.client.host if request.client else "unknown"
        auth = user.is_validate(method=body.auth_method, src_ip=client_ip)
        if auth is False:
            _signin_history(request, body.username, body.auth_method, False)
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cannot authenticate user. Error: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=401, detail="Authentication failed")

    # Re-fetch from DB so relationships (role) are loaded
    from powerdnsadmin.models.base import db as _db
    db_user = _db.session.query(User).filter_by(username=body.username).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = db_user

    # OTP check
    if user.otp_secret:
        if not body.otp_token:
            # Tell the SPA to show the OTP field
            return LoginResponse(status="otp_required", message="OTP token required")
        if not body.otp_token.isdigit() or not user.verify_totp(body.otp_token):
            _signin_history(request, body.username, body.auth_method, False)
            raise HTTPException(status_code=401, detail="Invalid OTP token")

    # LDAP autoprovisioning
    if Setting().get("autoprovisioning") and body.auth_method != "LOCAL":
        from powerdnsadmin.web.callbacks import checkForPDAEntries

        urn_value = Setting().get("urn_value")
        entitlements = user.read_entitlements(Setting().get("autoprovisioning_attribute"))
        if len(entitlements) == 0 and Setting().get("purge"):
            user.set_role("User")
            user.revoke_privilege(True)
        elif len(entitlements) != 0:
            if checkForPDAEntries(entitlements, urn_value):
                user.updateUser(entitlements)
            else:
                if Setting().get("purge"):
                    user.set_role("User")
                    user.revoke_privilege(True)

    # Set session
    session["user_id"] = user.id
    session["authentication_type"] = "LDAP" if body.auth_method != "LOCAL" else "LOCAL"
    _signin_history(request, user.username, body.auth_method, True)

    # Handle forced OTP setup
    if (Setting().get("otp_force")
            and Setting().get("otp_field_enabled")
            and not user.otp_secret):
        user.update_profile(enable_otp=True)
        session["welcome_user_id"] = user.id
        return LoginResponse(
            status="otp_setup_required",
            message="OTP setup required",
            user=_user_to_response(user),
        )

    return LoginResponse(
        status="ok",
        user=_user_to_response(user),
    )


@router.post("/logout")
async def logout(request: Request):
    """Clear the session, logging the user out."""
    session = _get_session(request)
    session.clear()
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    """Return current user info from the session.

    Returns 401 if not authenticated.
    """
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = _get_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.session.get(User, int(user_id))
    if user is None:
        session.clear()
        raise HTTPException(status_code=401, detail="User not found")

    return _user_to_response(user)


@router.get("/settings", response_model=AuthSettingsResponse)
async def auth_settings(request: Request):
    """Return public auth settings so the login page knows which providers to show.

    This endpoint does NOT require authentication.
    """
    from powerdnsadmin.models.setting import Setting

    config = get_config()

    return AuthSettingsResponse(
        local_db_enabled=Setting().get("local_db_enabled") or False,
        ldap_enabled=bool(Setting().get("ldap_enabled")),
        signup_enabled=bool(Setting().get("signup_enabled")),
        google_oauth_enabled=bool(Setting().get("google_oauth_enabled")),
        github_oauth_enabled=bool(Setting().get("github_oauth_enabled")),
        azure_oauth_enabled=bool(Setting().get("azure_oauth_enabled")),
        oidc_oauth_enabled=bool(Setting().get("oidc_oauth_enabled")),
        saml_enabled=config.get("SAML_ENABLED", False),
        otp_field_enabled=bool(Setting().get("otp_field_enabled")),
        verify_user_email=bool(Setting().get("verify_user_email")),
    )


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

class ProfileUpdateRequest(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    password: str | None = None


@router.get("/profile")
async def get_profile(request: Request):
    """Get current user's profile info."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = _get_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.session.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    auth_type = session.get("authentication_type", "LOCAL")

    return {
        "id": user.id,
        "username": user.username,
        "firstname": user.firstname or "",
        "lastname": user.lastname or "",
        "email": user.email or "",
        "role": user.role.name,
        "otp_enabled": bool(user.otp_secret),
        "auth_type": auth_type,
    }


@router.put("/profile")
async def update_profile(request: Request, body: ProfileUpdateRequest):
    """Update current user's profile. Only available for LOCAL auth users."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = _get_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.session.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if body.firstname is not None:
        user.firstname = body.firstname
    if body.lastname is not None:
        user.lastname = body.lastname
    if body.email is not None:
        # Check uniqueness
        existing = User.query.filter(
            User.email == body.email, User.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = body.email
    if body.password is not None:
        user.password = user.get_hashed_password(body.password)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "Profile updated"}


@router.post("/profile/otp")
async def toggle_otp(request: Request):
    """Enable or disable OTP for the current user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = _get_session(request)
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.session.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    body = await request.json()
    enable = body.get("enable", False)

    user.update_profile(enable_otp=enable)

    otp_uri = None
    if enable and user.otp_secret:
        otp_uri = user.get_totp_uri()

    return {
        "status": "ok",
        "otp_enabled": bool(user.otp_secret),
        "otp_uri": otp_uri,
    }
