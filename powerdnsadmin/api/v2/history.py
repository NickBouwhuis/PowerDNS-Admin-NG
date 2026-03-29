"""
API v2 history endpoints — session-based history for the SPA.
"""
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["history-v2"])


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


@router.get("")
async def list_history(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    domain_name: str = Query("", description="Filter by zone name"),
    user_name: str = Query("", description="Filter by username"),
    date_from: str = Query("", description="Start date (YYYY-MM-DD)"),
    date_to: str = Query("", description="End date (YYYY-MM-DD)"),
):
    """List history entries with optional filtering."""
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)

    # Check access
    is_admin = user.role.name in ["Administrator", "Operator"]
    if not is_admin and not Setting().get("allow_user_view_history"):
        raise HTTPException(status_code=403, detail="History access denied")

    query = History.query.order_by(History.created_on.desc())

    # Role-based filtering: non-admins see only their domain history
    if not is_admin:
        from powerdnsadmin.models.domain_user import DomainUser
        from powerdnsadmin.models.account import Account
        from powerdnsadmin.models.account_user import AccountUser
        from powerdnsadmin.models.base import db

        accessible_domain_ids = (
            db.session.query(Domain.id)
            .outerjoin(DomainUser, Domain.id == DomainUser.domain_id)
            .outerjoin(Account, Domain.account_id == Account.id)
            .outerjoin(AccountUser, Account.id == AccountUser.account_id)
            .filter(
                db.or_(
                    DomainUser.user_id == user.id,
                    AccountUser.user_id == user.id,
                )
            )
            .distinct()
        )
        query = query.filter(History.domain_id.in_(accessible_domain_ids))

    # Filters
    if domain_name:
        domain = Domain.query.filter(Domain.name == domain_name).first()
        if domain:
            query = query.filter(History.domain_id == domain.id)
        else:
            query = query.filter(History.msg.ilike(f"%{domain_name}%"))

    if user_name:
        query = query.filter(History.created_by == user_name)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.filter(History.created_on >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.filter(History.created_on < dt_to)
        except ValueError:
            pass

    total = query.count()
    offset = (page - 1) * per_page
    entries = query.offset(offset).limit(per_page).all()

    items = []
    for h in entries:
        detail = None
        if h.detail:
            try:
                detail = json.loads(h.detail)
            except (json.JSONDecodeError, TypeError):
                detail = h.detail

        items.append({
            "id": h.id,
            "msg": h.msg,
            "detail": detail,
            "created_by": h.created_by,
            "created_on": h.created_on.isoformat() if h.created_on else None,
            "domain_id": h.domain_id,
        })

    return {"total": total, "entries": items}


@router.delete("")
async def clear_history(request: Request):
    """Clear all history (admin only)."""
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    if user.role.name != "Administrator":
        raise HTTPException(status_code=403, detail="Only administrators can clear history")

    if Setting().get("preserve_history"):
        raise HTTPException(status_code=400, detail="History preservation is enabled")

    History().remove_all()

    # Log the clear action
    History(
        msg="Clear all history",
        created_by=user.username,
    ).add()

    return {"status": "ok", "message": "History cleared"}
