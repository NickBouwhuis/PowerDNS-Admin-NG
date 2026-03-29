"""
API v2 lookup endpoints — lightweight data for form dropdowns.

These endpoints provide account and template lists for the SPA forms.

Routes:
    GET /api/v2/lookups/accounts     — list accounts for current user
    GET /api/v2/lookups/templates    — list domain templates
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lookups", tags=["lookups-v2"])


class AccountItem(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class TemplateItem(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


def _get_authenticated_user(request: Request):
    """Get the authenticated user from the session or raise 401."""
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


@router.get("/accounts", response_model=list[AccountItem])
async def list_accounts(request: Request):
    """List accounts accessible to the current user.

    Admins/Operators see all accounts. Users see only their accounts.
    """
    from powerdnsadmin.models.account import Account

    user = _get_authenticated_user(request)

    if user.role.name in ["Administrator", "Operator"]:
        accounts = Account.query.order_by(Account.name).all()
    else:
        accounts = user.get_accounts()

    return [
        AccountItem(id=a.id, name=a.name, description=a.description)
        for a in accounts
    ]


@router.get("/templates", response_model=list[TemplateItem])
async def list_templates(request: Request):
    """List all domain templates."""
    from powerdnsadmin.models.domain_template import DomainTemplate

    _get_authenticated_user(request)

    templates = DomainTemplate.query.order_by(DomainTemplate.name).all()
    return [
        TemplateItem(id=t.id, name=t.name, description=t.description)
        for t in templates
    ]
