"""
API v2 search endpoint — global search across zones, records, and comments.
"""
import logging

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search-v2"])


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


@router.get("/search")
def global_search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
):
    """Search across zones, records, and comments via PowerDNS API."""
    from powerdnsadmin.models.server import Server
    from powerdnsadmin.models.domain import Domain

    user = _get_authenticated_user(request)
    is_admin = user.role.name in ["Administrator", "Operator"]

    try:
        results = Server(server_id="localhost").global_search(
            object_type="all", query=q
        )
    except Exception as e:
        logger.error("Global search failed: %s", e)
        raise HTTPException(status_code=502, detail="Search failed")

    # Get user's accessible domains for filtering
    allowed_domains = None
    if not is_admin:
        user_domains = user.get_user_domains()
        allowed_domains = set(d.name for d in user_domains)

    zones = []
    records = []
    comments = []

    for item in results:
        obj_type = item.get("object_type", "")
        # Clean up names (strip trailing dots)
        name = (item.get("name") or "").rstrip(".")
        zone_id = (item.get("zone_id") or "").rstrip(".")

        # Role-based filtering
        if allowed_domains is not None and zone_id not in allowed_domains:
            continue

        if obj_type == "zone":
            zones.append({
                "name": name,
                "zone_id": zone_id,
            })
        elif obj_type == "record":
            # Make name relative
            if name == zone_id:
                relative_name = "@"
            elif name.endswith("." + zone_id):
                relative_name = name[: -(len(zone_id) + 1)]
            else:
                relative_name = name

            records.append({
                "name": relative_name,
                "zone": zone_id,
                "type": item.get("type", ""),
                "content": item.get("content", ""),
                "ttl": item.get("ttl"),
                "disabled": item.get("disabled", False),
            })
        elif obj_type == "comment":
            relative_name = name
            if name == zone_id:
                relative_name = "@"
            elif name.endswith("." + zone_id):
                relative_name = name[: -(len(zone_id) + 1)]

            comments.append({
                "name": relative_name,
                "zone": zone_id,
                "content": item.get("content", ""),
            })

    return {
        "query": q,
        "zones": zones,
        "records": records,
        "comments": comments,
    }
