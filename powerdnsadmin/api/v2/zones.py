"""
API v2 zone endpoints — session-based zone management for the SPA.

Provides paginated, sortable, searchable zone listing and CRUD operations.
All endpoints use session auth (not HTTP Basic).

Routes:
    GET    /api/v2/zones                — paginated zone list
    POST   /api/v2/zones                — create zone
    DELETE /api/v2/zones/{zone_name}    — delete zone
    POST   /api/v2/zones/sync           — trigger zone sync from PowerDNS
"""
import json
import logging
import traceback

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zones", tags=["zones-v2"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ZoneListItem(BaseModel):
    id: int
    name: str
    type: str | None = None
    dnssec: bool = False
    serial: int | None = None
    notified_serial: int | None = None
    master: list[str] = []
    account: str | None = None
    account_id: int | None = None

    model_config = {"from_attributes": True}


class ZoneListResponse(BaseModel):
    total: int
    filtered: int
    zones: list[ZoneListItem]


class ZoneCreateRequest(BaseModel):
    name: str
    type: str = "Native"  # Native, Master, Slave
    soa_edit_api: str = "DEFAULT"
    nameservers: list[str] = []
    master_ips: list[str] = []
    account_id: int | None = None
    template_id: int | None = None


class ZoneCreateResponse(BaseModel):
    status: str
    message: str
    zone: ZoneListItem | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _require_admin_or_operator(user):
    """Raise 403 if user is not Administrator or Operator."""
    if user.role.name not in ["Administrator", "Operator"]:
        raise HTTPException(status_code=403, detail="Insufficient privileges")


def _domain_to_zone_item(domain) -> ZoneListItem:
    """Convert a Domain model instance to a ZoneListItem."""
    # Parse master field (stored as stringified list)
    master_list = []
    if domain.master:
        try:
            import ast
            parsed = ast.literal_eval(domain.master)
            if isinstance(parsed, list):
                master_list = parsed
        except (ValueError, SyntaxError):
            if domain.master.strip():
                master_list = [domain.master]

    account_name = None
    if domain.account:
        account_name = domain.account.name

    return ZoneListItem(
        id=domain.id,
        name=domain.name,
        type=domain.type,
        dnssec=bool(domain.dnssec),
        serial=domain.serial,
        notified_serial=domain.notified_serial,
        master=master_list,
        account=account_name,
        account_id=domain.account_id,
    )


def _user_can_create_domain(user):
    """Check if user is allowed to create domains."""
    from powerdnsadmin.models.setting import Setting

    if user.role.name in ["Administrator", "Operator"]:
        return True
    return bool(Setting().get("allow_user_create_domain"))


def _user_can_remove_domain(user):
    """Check if user is allowed to remove domains."""
    from powerdnsadmin.models.setting import Setting

    if user.role.name in ["Administrator", "Operator"]:
        return True
    return bool(Setting().get("allow_user_remove_domain"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=ZoneListResponse)
async def list_zones(
    request: Request,
    tab: str = Query("forward", pattern="^(forward|reverse_ipv4|reverse_ipv6)$"),
    search: str = Query("", description="Search filter for zone name / account"),
    sort_by: str = Query("name", description="Column to sort by"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
):
    """List zones with pagination, sorting, filtering, and tab-based grouping.

    Tabs:
    - forward: zones NOT ending in .in-addr.arpa or .ip6.arpa
    - reverse_ipv4: zones ending in .in-addr.arpa
    - reverse_ipv6: zones ending in .ip6.arpa
    """
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain_user import DomainUser
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.account_user import AccountUser
    from powerdnsadmin.models.base import db
    from sqlalchemy import not_

    user = _get_authenticated_user(request)

    # Base query with access control
    if user.role.name in ["Administrator", "Operator"]:
        query = Domain.query
    else:
        query = (
            db.session.query(Domain)
            .outerjoin(DomainUser, Domain.id == DomainUser.domain_id)
            .outerjoin(Account, Domain.account_id == Account.id)
            .outerjoin(AccountUser, Account.id == AccountUser.account_id)
            .filter(
                db.or_(
                    DomainUser.user_id == user.id,
                    AccountUser.user_id == user.id,
                )
            )
        )

    # Tab filtering
    tab_filters = {
        "reverse_ipv4": "%.in-addr.arpa",
        "reverse_ipv6": "%.ip6.arpa",
    }
    if tab in tab_filters:
        query = query.filter(Domain.name.ilike(tab_filters[tab]))
    else:
        # Forward zones: exclude reverse zones
        for pattern in tab_filters.values():
            query = query.filter(not_(Domain.name.ilike(pattern)))

    # Total count (before search)
    total = query.count()

    # Search
    if search:
        start_char = "" if search.startswith("^") else "%"
        end_char = "" if search.endswith("$") else "%"
        search_term = search.strip("^$")

        if user.role.name in ["Administrator", "Operator"]:
            query = query.outerjoin(Account).filter(
                Domain.name.ilike(f"{start_char}{search_term}{end_char}")
                | Account.name.ilike(f"{start_char}{search_term}{end_char}")
                | Account.description.ilike(f"{start_char}{search_term}{end_char}")
            )
        else:
            query = query.filter(
                Domain.name.ilike(f"{start_char}{search_term}{end_char}")
            )

    # Filtered count
    filtered = query.count()

    # Sorting
    sort_columns = {
        "name": Domain.name,
        "type": Domain.type,
        "serial": Domain.serial,
        "dnssec": Domain.dnssec,
        "master": Domain.master,
        "account": Domain.account_id,
    }
    sort_col = sort_columns.get(sort_by, Domain.name)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Pagination
    offset = (page - 1) * per_page
    domains = query.offset(offset).limit(per_page).all()

    zones = [_domain_to_zone_item(d) for d in domains]

    return ZoneListResponse(total=total, filtered=filtered, zones=zones)


@router.post("", response_model=ZoneCreateResponse, status_code=201)
async def create_zone(request: Request, body: ZoneCreateRequest):
    """Create a new DNS zone."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain_template import DomainTemplate
    from powerdnsadmin.models.domain_template_record import DomainTemplateRecord
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.record import Record
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.lib.utils import pretty_domain_name, to_idna

    user = _get_authenticated_user(request)

    if not _user_can_create_domain(user):
        raise HTTPException(status_code=403, detail="Domain creation not allowed")

    domain_name = body.name.strip()
    if domain_name.endswith("."):
        domain_name = domain_name[:-1]

    if " " in domain_name or not domain_name:
        raise HTTPException(status_code=400, detail="Invalid zone name")

    # Non-admin users must specify a valid account
    if user.role.name not in ["Administrator", "Operator"]:
        if not body.account_id:
            raise HTTPException(status_code=400, detail="Account is required")
        user_account_ids = [a.id for a in user.get_accounts()]
        if body.account_id not in user_account_ids:
            raise HTTPException(status_code=400, detail="Invalid account")

    # IDN encoding
    try:
        domain_name = to_idna(domain_name, "encode")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zone name (IDN encoding failed)")

    # Resolve account name
    account_name = ""
    if body.account_id:
        account_name = Account().get_name_by_id(body.account_id) or ""

    # Master IPs for slave zones
    master_ips = body.master_ips if body.type.lower() == "slave" else []

    # Check domain override
    if Setting().get("deny_domain_override"):
        d = Domain()
        upper_domain = d.is_overriding(domain_name)
        if upper_domain:
            raise HTTPException(
                status_code=409,
                detail=f"Zone already exists as a record under zone: {upper_domain}",
            )

    # Create zone
    d = Domain()
    result = d.add(
        domain_name=domain_name,
        domain_type=body.type.lower(),
        soa_edit_api=body.soa_edit_api,
        domain_master_ips=master_ips,
        account_name=account_name,
    )

    if result["status"] != "ok":
        raise HTTPException(status_code=400, detail=result.get("msg", "Zone creation failed"))

    domain_id = Domain().get_id_by_name(domain_name)

    # Record history
    History(
        msg="Add zone {}".format(pretty_domain_name(domain_name)),
        detail=json.dumps({
            "domain_type": body.type,
            "domain_master_ips": master_ips,
            "account_id": body.account_id,
        }),
        created_by=user.username,
        domain_id=domain_id,
    ).add()

    # Grant user access
    Domain(name=domain_name).grant_privileges([user.id])

    # Apply template if specified
    if body.template_id:
        template_obj = DomainTemplate.query.filter(
            DomainTemplate.id == body.template_id
        ).first()
        if template_obj:
            template_records = DomainTemplateRecord.query.filter(
                DomainTemplateRecord.template_id == body.template_id
            ).all()

            record_data = []
            for tr in template_records:
                record_data.append({
                    "record_data": tr.data,
                    "record_name": tr.name,
                    "record_status": "Active" if tr.status else "Disabled",
                    "record_ttl": tr.ttl,
                    "record_type": tr.type,
                    "comment_data": [{"content": tr.comment, "account": ""}],
                })

            r = Record()
            tpl_result = r.apply(domain_name, record_data)
            if tpl_result["status"] == "ok":
                History(
                    msg="Applying template {} to {} successfully.".format(
                        template_obj.name, domain_name
                    ),
                    detail=json.dumps({
                        "domain": domain_name,
                        "template": template_obj.name,
                        "add_rrsets": tpl_result["data"][0]["rrsets"],
                        "del_rrsets": tpl_result["data"][1]["rrsets"],
                    }),
                    created_by=user.username,
                    domain_id=domain_id,
                ).add()
            else:
                History(
                    msg="Failed to apply template {} to {}.".format(
                        template_obj.name, domain_name
                    ),
                    detail=json.dumps(tpl_result),
                    created_by=user.username,
                ).add()

    # Fetch the created domain for the response
    from powerdnsadmin.models.base import db
    domain = db.session.get(Domain, domain_id)
    zone_item = _domain_to_zone_item(domain) if domain else None

    return ZoneCreateResponse(
        status="ok",
        message=f"Zone {domain_name} created successfully",
        zone=zone_item,
    )


@router.post("/sync")
async def sync_zones(request: Request):
    """Trigger zone sync from PowerDNS to local database.

    Admin/Operator only.
    """
    from powerdnsadmin.models.domain import Domain

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    try:
        result = Domain().update()
        return {
            "status": result.get("status", "ok"),
            "message": result.get("msg", "Zone sync completed"),
        }
    except Exception as e:
        logger.error("Zone sync failed: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Zone sync failed")


# ---------------------------------------------------------------------------
# Zone detail endpoints (MUST be before catch-all DELETE)
# ---------------------------------------------------------------------------

def _require_zone_access(user, zone_name: str):
    """Check that user can access this zone. Returns the Domain object."""
    from powerdnsadmin.models.domain import Domain

    domain = Domain.query.filter(Domain.name == zone_name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Zone not found")

    if user.role.name not in ["Administrator", "Operator"]:
        if not Domain(id=domain.id).is_valid_access(user.id):
            raise HTTPException(status_code=403, detail="Access denied")

    return domain


@router.get("/detail/{zone_name}")
async def get_zone_detail(zone_name: str, request: Request):
    """Get zone detail including records from PowerDNS."""
    from powerdnsadmin.models.record import Record
    from powerdnsadmin.models.setting import Setting

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)

    try:
        rrsets = Record().get_rrsets(domain.name)
    except Exception as e:
        logger.error("Cannot fetch rrsets for %s: %s", zone_name, e)
        raise HTTPException(status_code=502, detail="Failed to fetch records from PowerDNS")

    # Determine which record types are editable
    editable_types = Setting().get_records_allow_to_edit()

    # Flatten rrsets into individual records for the frontend
    records = []
    for rrset in rrsets:
        r_name = rrset["name"].rstrip(".")
        # Strip zone suffix to get relative name
        if r_name == zone_name:
            relative_name = "@"
        elif r_name.endswith("." + zone_name):
            relative_name = r_name[: -(len(zone_name) + 1)]
        else:
            relative_name = r_name

        for idx, record in enumerate(rrset["records"]):
            comment = ""
            if idx < len(rrset.get("comments", [])):
                comment = rrset["comments"][idx].get("content", "")
            records.append({
                "name": relative_name,
                "type": rrset["type"],
                "ttl": rrset["ttl"],
                "content": record["content"],
                "disabled": record.get("disabled", False),
                "comment": comment,
                "is_allowed_edit": rrset["type"] in editable_types,
            })

    zone_item = _domain_to_zone_item(domain)

    return {
        "zone": zone_item.model_dump(),
        "records": records,
        "editable_types": editable_types,
    }


@router.patch("/detail/{zone_name}/records")
async def apply_records(zone_name: str, request: Request):
    """Apply record changes to a zone.

    Expects JSON body with a list of all records (the full desired state).
    The backend compares with current state and computes the delta.
    """
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.record import Record
    from powerdnsadmin.models.history import History
    from powerdnsadmin.lib.utils import pretty_domain_name

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)

    body = await request.json()
    submitted_records = body.get("records", [])

    r = Record()
    try:
        result = r.apply(domain.name, submitted_records)
    except Exception as e:
        logger.error("Cannot apply records to %s: %s", zone_name, e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

    if result["status"] != "ok":
        raise HTTPException(status_code=400, detail=result.get("msg", "Failed to apply records"))

    # Log history
    History(
        msg="Apply record changes to zone {}".format(pretty_domain_name(zone_name)),
        detail=json.dumps({
            "domain": zone_name,
            "add_rrsets": result["data"][0]["rrsets"],
            "del_rrsets": result["data"][1]["rrsets"],
        }),
        created_by=user.username,
        domain_id=domain.id,
    ).add()

    return {"status": "ok", "message": "Records applied successfully"}


@router.post("/detail/{zone_name}/notify")
async def notify_zone(zone_name: str, request: Request):
    """Send DNS NOTIFY to slave servers."""
    from powerdnsadmin.services.pdns_client import PowerDNSClient

    user = _get_authenticated_user(request)
    _require_zone_access(user, zone_name)

    try:
        client = PowerDNSClient()
        result = client.notify_zone(zone_name)
        return {"status": "ok", "message": "NOTIFY sent"}
    except Exception as e:
        logger.error("Failed to send NOTIFY for %s: %s", zone_name, e)
        raise HTTPException(status_code=500, detail="Failed to send NOTIFY")


@router.post("/detail/{zone_name}/axfr")
async def axfr_zone(zone_name: str, request: Request):
    """Trigger AXFR for a slave zone."""
    from powerdnsadmin.models.domain import Domain

    user = _get_authenticated_user(request)
    _require_zone_access(user, zone_name)

    d = Domain()
    result = d.update_from_master(zone_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "AXFR failed"))
    return {"status": "ok", "message": result.get("msg", "AXFR completed")}


@router.get("/detail/{zone_name}/changelog")
async def get_changelog(
    zone_name: str,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Get zone changelog (history entries)."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)

    query = (
        History.query
        .filter(History.domain_id == domain.id)
        .order_by(History.created_on.desc())
    )

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
        })

    return {"total": total, "entries": items}


@router.get("/detail/{zone_name}/dnssec")
async def get_dnssec(zone_name: str, request: Request):
    """Get DNSSEC keys for a zone."""
    from powerdnsadmin.models.domain import Domain

    user = _get_authenticated_user(request)
    _require_zone_access(user, zone_name)

    d = Domain()
    result = d.get_domain_dnssec(zone_name)
    if result.get("status") == "error":
        return {"enabled": False, "keys": [], "message": result.get("msg", "")}

    return {"enabled": True, "keys": result.get("dnssec", [])}


@router.post("/detail/{zone_name}/dnssec/enable")
async def enable_dnssec(zone_name: str, request: Request):
    """Enable DNSSEC for a zone."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)

    # Check permission
    from powerdnsadmin.models.setting import Setting
    if user.role.name not in ["Administrator", "Operator"] and Setting().get("dnssec_admins_only"):
        raise HTTPException(status_code=403, detail="DNSSEC configuration restricted to admins")

    d = Domain()
    result = d.enable_domain_dnssec(zone_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "Failed to enable DNSSEC"))

    History(
        msg="DNSSEC was enabled for zone {}".format(zone_name),
        created_by=user.username,
        domain_id=domain.id,
    ).add()

    # Return the new keys
    keys_result = d.get_domain_dnssec(zone_name)
    return {
        "status": "ok",
        "message": "DNSSEC enabled",
        "keys": keys_result.get("dnssec", []),
    }


@router.delete("/detail/{zone_name}/dnssec")
async def disable_dnssec(zone_name: str, request: Request):
    """Disable DNSSEC for a zone (delete all keys)."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)

    from powerdnsadmin.models.setting import Setting
    if user.role.name not in ["Administrator", "Operator"] and Setting().get("dnssec_admins_only"):
        raise HTTPException(status_code=403, detail="DNSSEC configuration restricted to admins")

    d = Domain()
    dnssec_info = d.get_domain_dnssec(zone_name)
    if dnssec_info.get("status") == "error":
        raise HTTPException(status_code=400, detail="DNSSEC is not enabled for this zone")

    for key in dnssec_info.get("dnssec", []):
        result = d.delete_dnssec_key(zone_name, key["id"])
        if result and result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg", "Failed to disable DNSSEC"))

    History(
        msg="DNSSEC was disabled for zone {}".format(zone_name),
        created_by=user.username,
        domain_id=domain.id,
    ).add()

    return {"status": "ok", "message": "DNSSEC disabled"}


@router.get("/detail/{zone_name}/settings")
async def get_zone_settings(zone_name: str, request: Request):
    """Get zone settings (type, SOA, account, user access)."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.account import Account

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)
    _require_admin_or_operator(user)

    # Fetch zone info from PowerDNS
    d = Domain()
    domain_info = d.get_domain_info(zone_name)

    # Get current domain users
    domain_user_ids = Domain(name=zone_name).get_user()

    # Get all users for user assignment dropdown
    all_users = User.query.order_by(User.username).all()
    users = [{"id": u.id, "username": u.username} for u in all_users]

    # Get all accounts
    accounts = Account.query.order_by(Account.name).all()
    account_list = [{"id": a.id, "name": a.name} for a in accounts]

    return {
        "zone_type": domain_info.get("kind", "").lower() if domain_info else "",
        "masters": domain_info.get("masters", []) if domain_info else [],
        "soa_edit_api": (domain_info.get("soa_edit_api", "DEFAULT") or "DEFAULT").upper() if domain_info else "DEFAULT",
        "account_id": domain.account_id,
        "account_name": domain.account.name if domain.account else None,
        "domain_user_ids": domain_user_ids,
        "users": users,
        "accounts": account_list,
    }


@router.put("/detail/{zone_name}/settings")
async def update_zone_settings(zone_name: str, request: Request):
    """Update zone settings."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.history import History
    from powerdnsadmin.lib.utils import pretty_domain_name

    user = _get_authenticated_user(request)
    domain = _require_zone_access(user, zone_name)
    _require_admin_or_operator(user)

    body = await request.json()
    d = Domain()
    results = []

    # Update zone type
    if "zone_type" in body:
        zone_type = body["zone_type"]
        masters = body.get("masters", [])
        if isinstance(masters, str):
            masters = [m.strip() for m in masters.split(",") if m.strip()]
        status = d.update_kind(domain_name=zone_name, kind=zone_type, masters=masters)
        if status and status.get("status") == "error":
            results.append({"field": "zone_type", "error": status.get("msg")})
        else:
            History(
                msg="Change zone {} type to {}".format(pretty_domain_name(zone_name), zone_type),
                created_by=user.username,
                domain_id=domain.id,
            ).add()

    # Update SOA-EDIT-API
    if "soa_edit_api" in body:
        soa = body["soa_edit_api"]
        status = d.update_soa_setting(domain_name=zone_name, soa_edit_api=soa)
        if status and status.get("status") == "error":
            results.append({"field": "soa_edit_api", "error": status.get("msg")})
        else:
            History(
                msg="Change SOA-EDIT-API for zone {} to {}".format(pretty_domain_name(zone_name), soa),
                created_by=user.username,
                domain_id=domain.id,
            ).add()

    # Update account
    if "account_id" in body:
        account_id = body["account_id"]
        Domain(name=zone_name).assoc_account(
            account_id=account_id,
            update=True,
            created_by=user.username,
        )

    # Update user access
    if "user_ids" in body:
        new_user_ids = body["user_ids"]
        Domain(name=zone_name).grant_privileges(new_user_ids)
        # Build user list for history
        usernames = [u.username for u in User.query.filter(User.id.in_(new_user_ids)).all()]
        History(
            msg="Change zone {} access control".format(pretty_domain_name(zone_name)),
            detail=json.dumps({"user_has_access": usernames}),
            created_by=user.username,
            domain_id=domain.id,
        ).add()

    if any(r.get("error") for r in results):
        errors = [r for r in results if r.get("error")]
        raise HTTPException(status_code=400, detail=errors[0]["error"])

    return {"status": "ok", "message": "Settings updated"}


# ---------------------------------------------------------------------------
# Catch-all DELETE (MUST be last)
# ---------------------------------------------------------------------------

@router.delete("/{zone_name}")
async def delete_zone(zone_name: str, request: Request):
    """Delete a DNS zone."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.lib.utils import pretty_domain_name

    user = _get_authenticated_user(request)

    if not _user_can_remove_domain(user):
        raise HTTPException(status_code=403, detail="Domain removal not allowed")

    # Access control for non-admin users
    if user.role.name not in ["Administrator", "Operator"]:
        domain = Domain.query.filter(Domain.name == zone_name).first()
        if not domain:
            raise HTTPException(status_code=404, detail="Zone not found")
        if not Domain(id=domain.id).is_valid_access(user.id):
            raise HTTPException(status_code=403, detail="Access denied")

    d = Domain()
    result = d.delete(zone_name)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "Zone deletion failed"))

    History(
        msg="Remove zone {}".format(pretty_domain_name(zone_name)),
        detail=json.dumps({"zone": zone_name}),
        created_by=user.username,
    ).add()

    return {"status": "ok", "message": f"Zone {zone_name} deleted"}
