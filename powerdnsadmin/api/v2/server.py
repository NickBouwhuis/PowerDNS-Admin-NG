"""
API v2 server endpoints — PDNS server statistics and configuration.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/server", tags=["server-v2"])


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


@router.get("/statistics")
def get_statistics(request: Request):
    """Get PowerDNS server statistics."""
    from powerdnsadmin.models.server import Server
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.history import History

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    try:
        stats = Server(server_id="localhost").get_statistic()
    except Exception as e:
        logger.error("Failed to fetch PDNS statistics: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch statistics")

    # Extract key metrics
    uptime = None
    if isinstance(stats, list):
        for s in stats:
            if s.get("name") == "uptime":
                uptime = int(s["value"])
                break
        # Normalize: ensure every stat value is a string for JSON consistency.
        # MapStatisticItem/RingStatisticItem have list values — convert to JSON.
        import json as _json
        for s in stats:
            if not isinstance(s.get("value"), str):
                s["value"] = _json.dumps(s["value"])

    # DB counts
    zone_count = Domain.query.count()
    user_count = User.query.count()
    history_count = History.query.count()

    return {
        "pdns_stats": stats if isinstance(stats, list) else [],
        "uptime": uptime,
        "zone_count": zone_count,
        "user_count": user_count,
        "history_count": history_count,
    }


@router.get("/configuration")
def get_configuration(request: Request):
    """Get PowerDNS server configuration."""
    from powerdnsadmin.models.server import Server

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    try:
        config = Server(server_id="localhost").get_config()
    except Exception as e:
        logger.error("Failed to fetch PDNS configuration: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch configuration")

    return {
        "config": config if isinstance(config, list) else [],
    }
