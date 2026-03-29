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
import json
import logging
from typing import Union
from urllib.parse import urljoin

import requests as http_requests
from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select

logger = logging.getLogger(__name__)


def db_session_cleanup():
    """Ensure the scoped DB session is cleaned up for every request.

    Because FastAPI runs sync generator dependencies via run_in_threadpool,
    the teardown may execute on a *different* thread than the route handler.
    Since db.session is thread-local (scoped_session), that means the
    teardown could miss the poisoned session.

    Fix: remove any stale session at the START (runs on the route handler's
    thread, guaranteed to hit the right thread-local).
    """
    from powerdnsadmin.models.base import db
    if db._scoped_session is not None:
        db.session.remove()
    try:
        yield
    except Exception:
        if db._scoped_session is not None:
            db.session.rollback()
        raise
    finally:
        if db._scoped_session is not None:
            db.session.remove()


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
        # Rollback the failed transaction on this thread before it poisons
        # subsequent requests.  The async middleware's cleanup runs on the
        # event-loop thread and cannot reach this thread-local session.
        from powerdnsadmin.models.base import db
        db.session.rollback()
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

    apikey = ApiKey(key=apikey_val)
    apikey.plain_text_password = apikey_val

    try:
        validated = apikey.is_validate(
            method="LOCAL",
            src_ip=request.client.host if request.client else "",
        )
    except Exception as e:
        # Rollback the failed transaction on this thread before it poisons
        # subsequent requests.  The async middleware's cleanup runs on the
        # event-loop thread and cannot reach this thread-local session.
        from powerdnsadmin.models.base import db
        db.session.rollback()
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

        if apikey.role.name not in roles:
            raise HTTPException(
                status_code=401,
                detail="API key does not have sufficient privileges",
            )

        return apikey

    return dependency


# ── API Key domain-access dependencies ──────────────────────────────


def apikey_can_access_domain(
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """Check that the API key has access to the requested zone.

    Replaces @apikey_can_access_domain decorator.
    Admin/Operator keys have unrestricted access.
    User keys must have the zone explicitly assigned (directly or via account).
    """
    if apikey.role.name in ("Administrator", "Operator"):
        return apikey

    zone_id = request.path_params.get("zone_id", "").rstrip(".")
    if not zone_id:
        return apikey

    domain_names = [item.name for item in apikey.domains]
    accounts_domains = [d.name for a in apikey.accounts for d in a.domains]
    allowed = set(domain_names + accounts_domains)

    if zone_id not in allowed:
        raise HTTPException(status_code=403, detail="Zone access not allowed")

    return apikey


def apikey_can_create_domain(
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """Check API key can create zones (replaces @apikey_can_create_domain).

    Admins/Operators always can. Users need allow_user_create_domain setting.
    Also checks deny_domain_override if enabled.
    """
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.domain import Domain

    if (apikey.role.name not in ("Administrator", "Operator")
            and not Setting().get("allow_user_create_domain")):
        raise HTTPException(
            status_code=401,
            detail="API key does not have enough privileges to create zone",
        )

    if Setting().get("deny_domain_override"):
        try:
            body = json.loads(request._body) if hasattr(request, '_body') else {}
        except (json.JSONDecodeError, TypeError):
            body = {}
        name = body.get("name")
        if name and Domain().is_overriding(name):
            raise HTTPException(
                status_code=409,
                detail="Zone override of record not allowed",
            )

    return apikey


def apikey_can_remove_domain(
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """Check API key can remove zones (replaces @apikey_can_remove_domain).

    Only checked for DELETE requests.
    """
    from powerdnsadmin.models.setting import Setting

    if request.method != "DELETE":
        return apikey

    if (apikey.role.name not in ("Administrator", "Operator")
            and not Setting().get("allow_user_remove_domain")):
        raise HTTPException(
            status_code=401,
            detail="API key does not have enough privileges to remove zone",
        )

    return apikey


def apikey_can_configure_dnssec(
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """Check API key can configure DNSSEC (replaces @apikey_can_configure_dnssec)."""
    from powerdnsadmin.models.setting import Setting

    if (apikey.role.name not in ("Administrator", "Operator")
            and Setting().get("dnssec_admins_only")):
        raise HTTPException(
            status_code=403,
            detail="API key does not have enough privileges to configure DNSSEC",
        )

    return apikey


def user_can_create_domain(
    request: Request,
    user=Depends(get_current_user),
):
    """Check user can create zones (replaces @api_can_create_domain).

    Admins/Operators always can. Users need allow_user_create_domain setting.
    """
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.domain import Domain

    if (user.role.name not in ("Administrator", "Operator")
            and not Setting().get("allow_user_create_domain")):
        raise HTTPException(
            status_code=401,
            detail="User does not have enough privileges to create zone",
        )

    if Setting().get("deny_domain_override"):
        try:
            body = json.loads(request._body) if hasattr(request, '_body') else {}
        except (json.JSONDecodeError, TypeError):
            body = {}
        name = body.get("name")
        if name and Domain().is_overriding(name):
            raise HTTPException(
                status_code=409,
                detail="Zone override of record not allowed",
            )

    return user


# ── PowerDNS API forwarding ─────────────────────────────────────────


async def forward_to_pdns(request: Request) -> Response:
    """Forward a FastAPI request to the PowerDNS API.

    Replaces helper.forward_request() for FastAPI routes.
    Returns a FastAPI Response with the PowerDNS API response data.
    """
    from powerdnsadmin.models.setting import Setting

    setting = Setting()
    api_url = setting.get("pdns_api_url")
    api_key = setting.get("pdns_api_key")
    verify_ssl = setting.get("verify_ssl_connections")

    # Build target URL: base URL + the original request path + query string
    path = request.url.path
    query = str(request.url.query) if request.url.query else ""
    target_url = urljoin(api_url, path)
    if query:
        target_url += "?" + query

    headers = {
        "X-API-Key": api_key,
        "user-agent": "powerdns-admin/api",
        "pragma": "no-cache",
        "cache-control": "no-cache",
        "accept": "application/json; q=1",
    }

    body = None
    if request.method not in ("GET", "DELETE"):
        body = await request.body()
        if body:
            headers["Content-Type"] = "application/json"

    logger.debug("Forwarding %s %s to PowerDNS API", request.method, target_url)

    resp = http_requests.request(
        request.method,
        target_url,
        headers=headers,
        verify=bool(verify_ssl),
        data=body,
    )

    # Build response headers, excluding hop-by-hop headers
    excluded_headers = {"transfer-encoding", "connection", "keep-alive"}
    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded_headers
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
    )
