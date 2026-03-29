"""
FastAPI web dependencies for authentication and authorization.

These replace the Flask decorators in decorators.py for web UI routes.
They work with server-side sessions (not HTTP Basic auth like the API deps).

Usage:
    @router.get("/dashboard/")
    async def dashboard(request: Request, user=Depends(require_login)):
        ...

    @router.get("/admin/users")
    async def manage_users(request: Request, user=Depends(require_role("Administrator"))):
        ...
"""
import logging

from fastapi import Depends, HTTPException, Request
from starlette.responses import RedirectResponse

logger = logging.getLogger(__name__)


def get_session(request: Request) -> dict:
    """Get the session dict from request state."""
    session = getattr(request.state, 'session', None)
    if session is None:
        raise HTTPException(status_code=500, detail="Session middleware not configured")
    return session


def get_current_user(request: Request):
    """Load the current user from the session.

    Returns the User model instance or None if not authenticated.
    """
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    session = getattr(request.state, 'session', None)
    if session is None:
        return None

    user_id = session.get('user_id')
    if not user_id:
        return None

    return db.session.get(User, int(user_id))


async def require_login(request: Request):
    """Dependency that requires an authenticated user.

    Redirects to /login if not authenticated (for web UI routes).
    """
    user = get_current_user(request)
    if user is None:
        session = getattr(request.state, 'session', None)
        if session is not None:
            session['next'] = str(request.url.path)
        raise HTTPException(
            status_code=302,
            headers={"Location": "/login"},
        )
    return user


def require_role(*roles: str):
    """Factory returning a dependency that checks user role.

    Redirects to /login if not authenticated, returns 403 if wrong role.

    Usage:
        user = Depends(require_role("Administrator"))
        user = Depends(require_role("Administrator", "Operator"))
    """
    if not roles:
        roles = ("Administrator", "Operator")

    async def dependency(request: Request):
        user = get_current_user(request)
        if user is None:
            session = getattr(request.state, 'session', None)
            if session is not None:
                session['next'] = str(request.url.path)
            raise HTTPException(
                status_code=302,
                headers={"Location": "/login"},
            )
        if user.role.name not in roles:
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user

    return dependency


async def require_history_access(request: Request):
    """Dependency for history access.

    Allows Admins/Operators, or Users if allow_user_view_history is enabled.
    """
    from powerdnsadmin.models.setting import Setting

    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if user.role.name not in ['Administrator', 'Operator'] \
            and not Setting().get('allow_user_view_history'):
        raise HTTPException(status_code=403, detail="History access denied")

    return user


async def can_access_domain(request: Request, domain_name: str):
    """Dependency for domain access checks.

    Allows Admins/Operators, or users with explicit domain/account access.
    """
    from powerdnsadmin.models.domain import Domain

    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if user.role.name in ['Administrator', 'Operator']:
        return user

    domain = Domain.query.filter(Domain.name == domain_name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if not Domain(id=domain.id).is_valid_access(user.id):
        raise HTTPException(status_code=403, detail="Domain access denied")

    return user


async def can_create_domain(request: Request):
    """Dependency for domain creation permission."""
    from powerdnsadmin.models.setting import Setting

    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if user.role.name in ['Administrator', 'Operator']:
        return user

    if not Setting().get('allow_user_create_domain'):
        raise HTTPException(status_code=403, detail="Domain creation not allowed")

    return user


async def can_remove_domain(request: Request):
    """Dependency for domain removal permission."""
    from powerdnsadmin.models.setting import Setting

    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if user.role.name in ['Administrator', 'Operator']:
        return user

    if not Setting().get('allow_user_remove_domain'):
        raise HTTPException(status_code=403, detail="Domain removal not allowed")

    return user


async def can_configure_dnssec(request: Request):
    """Dependency for DNSSEC configuration permission."""
    from powerdnsadmin.models.setting import Setting

    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

    if user.role.name in ['Administrator', 'Operator']:
        return user

    if Setting().get('dnssec_admins_only'):
        raise HTTPException(status_code=403, detail="DNSSEC admins only")

    return user
