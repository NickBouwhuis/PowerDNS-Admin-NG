"""
FastAPI dependency injection for authentication and authorization.

Replaces Flask decorators (api_basic_auth, apikey_auth, api_role_can, etc.)
with FastAPI Depends() callables.

Usage in route functions:
    @router.get("/zones")
    def list_zones(user: User = Depends(get_current_user)):
        ...

    @router.post("/zones")
    def create_zone(user: User = Depends(require_role("Operator"))):
        ...

    @router.get("/servers/{server_id}/zones")
    def list_zones(apikey: ApiKey = Depends(get_current_apikey)):
        ...
"""
import base64
import binascii
import logging
from typing import Union

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _get_flask_app(request: Request):
    """Retrieve the Flask app stored on FastAPI state."""
    return request.app.state.flask_app


def _get_db_session(request: Request):
    """Get a SQLAlchemy session from Flask-SQLAlchemy.

    Pushes a Flask app context so that Flask-SQLAlchemy's
    scoped session works correctly.
    """
    flask_app = _get_flask_app(request)
    ctx = flask_app.app_context()
    ctx.push()
    try:
        from powerdnsadmin.models.base import db
        yield db.session
    finally:
        ctx.pop()


def get_current_user(
    request: Request,
    authorization: str = Header(None),
    auth_method: str = Query("LOCAL"),
):
    """Authenticate via HTTP Basic auth (replaces @api_basic_auth).

    Returns the authenticated User model instance.
    Raises HTTPException(401) on failure.
    """
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.setting import Setting

    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")

    try:
        decoded = base64.b64decode(authorization[6:]).decode("utf-8")
        parts = decoded.split(":", maxsplit=1)
    except (binascii.Error, UnicodeDecodeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid base64 credentials")

    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid credential format")

    username, password = parts

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        user = User(username=username, password=password,
                    plain_text_password=password)

        # Check email verification if enabled
        if Setting().get('verify_user_email') and user.email and not user.confirmed:
            raise HTTPException(status_code=401, detail="Email not verified")

        method = "LDAP" if auth_method != "LOCAL" else "LOCAL"
        try:
            if not user.is_validate(method=method, src_ip=request.client.host if request.client else ""):
                raise HTTPException(status_code=401, detail="Invalid credentials")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Auth error: %s", e)
            raise HTTPException(status_code=401, detail="Authentication failed")

        # Re-fetch the full user object from DB
        from powerdnsadmin.models.base import db
        authenticated_user = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not authenticated_user:
            raise HTTPException(status_code=401, detail="User not found")

        return authenticated_user


def get_current_apikey(
    request: Request,
    x_api_key: str = Header(None),
):
    """Authenticate via X-API-KEY header (replaces @apikey_auth).

    Returns the authenticated ApiKey model instance.
    Raises HTTPException(401) on failure.
    """
    from powerdnsadmin.models.api_key import ApiKey

    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")

    try:
        apikey_val = base64.b64decode(x_api_key).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid base64-encoded API key")

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        apikey = ApiKey(key=apikey_val)
        apikey.plain_text_password = apikey_val

        try:
            validated = apikey.is_validate(
                method="LOCAL",
                src_ip=request.client.host if request.client else "",
            )
        except Exception as e:
            logger.error("API key auth error: %s", e)
            raise HTTPException(status_code=401, detail="Invalid API key")

        return validated


def get_current_user_or_apikey(
    request: Request,
    authorization: str = Header(None),
    x_api_key: str = Header(None),
    auth_method: str = Query("LOCAL"),
) -> Union["User", "ApiKey"]:
    """Authenticate via either Basic auth or API key (replaces @apikey_or_basic_auth).

    Prefers API key if X-API-KEY header is present, otherwise falls back to Basic auth.
    """
    if x_api_key:
        return get_current_apikey(request, x_api_key)
    return get_current_user(request, authorization, auth_method)


def require_role(*roles: str, allow_self: bool = False):
    """Factory returning a dependency that checks user role.

    Replaces @api_role_can decorator.

    Usage:
        user: User = Depends(require_role("Administrator", "Operator"))
        user: User = Depends(require_role("Administrator", allow_self=True))
    """
    if not roles:
        roles = ("Administrator", "Operator")

    def dependency(
        request: Request,
        authorization: str = Header(None),
        auth_method: str = Query("LOCAL"),
    ):
        user = get_current_user(request, authorization, auth_method)

        if user.role.name in roles:
            return user

        if allow_self:
            # Check path parameters for self-access
            path_params = request.path_params
            try:
                user_id = int(path_params.get("user_id", 0))
                if user_id and user.id == user_id:
                    return user
            except (TypeError, ValueError):
                pass

            username = path_params.get("username")
            if username and user.username == username:
                return user

        raise HTTPException(
            status_code=401,
            detail="User {0} with role {1} does not have enough privileges".format(
                user.username, user.role.name),
        )

    return dependency


def require_apikey_role(*roles: str):
    """Factory returning a dependency that checks API key role.

    Usage:
        apikey: ApiKey = Depends(require_apikey_role("Administrator"))
    """
    if not roles:
        roles = ("Administrator", "Operator")

    def dependency(
        request: Request,
        x_api_key: str = Header(None),
    ):
        apikey = get_current_apikey(request, x_api_key)

        flask_app = _get_flask_app(request)
        with flask_app.app_context():
            if apikey.role.name not in roles:
                raise HTTPException(
                    status_code=401,
                    detail="API key does not have sufficient privileges",
                )

        return apikey

    return dependency
