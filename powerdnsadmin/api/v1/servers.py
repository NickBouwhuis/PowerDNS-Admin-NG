"""PowerDNS server pass-through endpoints (API key auth).

These endpoints proxy requests to the PowerDNS API with access control.
They correspond to the Flask endpoints:
  - GET/POST   /api/v1/servers/{server_id}/zones
  - GET/PUT/PATCH/DELETE /api/v1/servers/{server_id}/zones/{zone_id}
  - Various subpath forwards
  - GET /api/v1/servers
  - GET /api/v1/servers/{server_id}
  - GET /api/v1/sync_domains
  - GET /api/v1/servers/{server_id}/zones/{zone_id}/cryptokeys
  - etc.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..deps import (
    forward_to_pdns,
    get_current_apikey,
    get_current_user_or_apikey,
    apikey_can_access_domain,
    apikey_can_create_domain,
    apikey_can_configure_dnssec,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["servers"])


def _is_custom_header_api(request: Request, apikey):
    """Get the creator name for history, respecting custom header setting."""
    from powerdnsadmin.models.setting import Setting

    custom_header_setting = Setting().get("custom_history_header")
    if custom_header_setting and custom_header_setting in request.headers:
        return request.headers[custom_header_setting]
    return apikey.description


# ── Zone list / create (API key auth) ───────────────────────────────


@router.get("/servers/{server_id}/zones")
async def get_zones(
    server_id: str,
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """List zones. If server_id == 'pdnsadmin', returns from local DB."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.schemas import ZoneSummary

    if server_id == "pdnsadmin":
        if apikey.role.name in ("Administrator", "Operator"):
            domains = Domain.query.all()
        else:
            domains = apikey.domains
        return [ZoneSummary.model_validate(d).model_dump() for d in domains]

    # Forward to PowerDNS
    resp = await forward_to_pdns(request)

    # Filter zones for User role
    if apikey.role.name not in ("Administrator", "Operator") and resp.status_code == 200:
        domain_names = [d.name for d in apikey.domains]
        account_domains = [d.name for a in apikey.accounts for d in a.domains]
        allowed = set(domain_names + account_domains)

        try:
            all_zones = json.loads(resp.body)
            filtered = [z for z in all_zones if z["name"].rstrip(".") in allowed]
            return JSONResponse(
                content=filtered,
                status_code=resp.status_code,
            )
        except (json.JSONDecodeError, KeyError):
            pass

    return resp


@router.post("/servers/{server_id}/zones", status_code=201)
async def create_zone(
    server_id: str,
    request: Request,
    apikey=Depends(apikey_can_create_domain),
):
    """Create a zone via PowerDNS API (API key auth)."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History

    resp = await forward_to_pdns(request)

    if resp.status_code == 201:
        created_by = _is_custom_header_api(request, apikey)
        try:
            data = json.loads(resp.body) if resp.body else {}
        except json.JSONDecodeError:
            data = {}
        zone_name = data.get("name", "").rstrip(".")

        if apikey.role.name not in ("Administrator", "Operator"):
            domain = Domain(name=zone_name)
            apikey.domains.append(domain)

        domain = Domain()
        domain.update()

        history = History(
            msg="Add zone {}".format(zone_name),
            detail=json.dumps(data),
            created_by=created_by,
            domain_id=domain.get_id_by_name(zone_name),
        )
        history.add()

    return resp


# ── Single zone operations (API key auth) ────────────────────────────


@router.get("/servers/{server_id}/zones/{zone_id}")
async def get_zone(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Get zone details from PowerDNS."""
    return await forward_to_pdns(request)


@router.put("/servers/{server_id}/zones/{zone_id}")
async def update_zone(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Update zone metadata. Checks DNSSEC config if dnssec/nsec3param in body."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting

    # Check DNSSEC permissions if body contains dnssec/nsec3param keys
    body = await request.body()
    try:
        body_data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        body_data = {}

    if "dnssec" in body_data or "nsec3param" in body_data:
        if (apikey.role.name not in ("Administrator", "Operator")
                and Setting().get("dnssec_admins_only")):
            raise HTTPException(
                status_code=403,
                detail="API key does not have enough privileges to configure DNSSEC",
            )

    resp = await forward_to_pdns(request)

    if not Setting().get("bg_domain_updates"):
        Domain().update()

    if 200 <= resp.status_code < 300 and Setting().get("enable_api_rr_history"):
        created_by = _is_custom_header_api(request, apikey)
        history = History(
            msg="Updated zone {}".format(zone_id.rstrip(".")),
            detail="",
            created_by=created_by,
            domain_id=Domain().get_id_by_name(zone_id.rstrip(".")),
        )
        history.add()

    return resp


@router.patch("/servers/{server_id}/zones/{zone_id}")
async def patch_zone(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Patch zone records (add/replace/delete rrsets)."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting

    # Validate record types/TTL for User role
    body = await request.body()
    try:
        body_data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        body_data = {}

    if apikey.role.name not in ("Administrator", "Operator"):
        _validate_rrset_types(body_data)
        _validate_rrset_ttl(body_data)

    resp = await forward_to_pdns(request)

    if not Setting().get("bg_domain_updates"):
        Domain().update()

    if 200 <= resp.status_code < 300 and Setting().get("enable_api_rr_history"):
        created_by = _is_custom_header_api(request, apikey)
        rrsets = body_data.get("rrsets", [])
        history = History(
            msg="Apply record changes to zone {}".format(zone_id.rstrip(".")),
            detail=json.dumps({
                "domain": zone_id.rstrip("."),
                "add_rrsets": [r for r in rrsets if r.get("changetype") == "REPLACE"],
                "del_rrsets": [r for r in rrsets if r.get("changetype") == "DELETE"],
            }),
            created_by=created_by,
            domain_id=Domain().get_id_by_name(zone_id.rstrip(".")),
        )
        history.add()

    return resp


@router.delete("/servers/{server_id}/zones/{zone_id}")
async def delete_zone(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Delete a zone via PowerDNS API."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting

    # Check removal permission
    if (apikey.role.name not in ("Administrator", "Operator")
            and not Setting().get("allow_user_remove_domain")):
        raise HTTPException(
            status_code=401,
            detail="API key does not have enough privileges to remove zone",
        )

    resp = await forward_to_pdns(request)

    if not Setting().get("bg_domain_updates"):
        Domain().update()

    if 200 <= resp.status_code < 300 and Setting().get("enable_api_rr_history"):
        created_by = _is_custom_header_api(request, apikey)
        history = History(
            msg="Deleted zone {}".format(zone_id.rstrip(".")),
            detail="",
            created_by=created_by,
            domain_id=Domain().get_id_by_name(zone_id.rstrip(".")),
        )
        history.add()

    return resp


# ── Cryptokey endpoints (MUST be before the catch-all subpath route) ─


@router.get("/servers/{server_id}/zones/{zone_id}/cryptokeys")
async def get_cryptokeys(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Get DNSSEC cryptokeys for a zone."""
    return await forward_to_pdns(request)


@router.post("/servers/{server_id}/zones/{zone_id}/cryptokeys")
async def create_cryptokey(
    server_id: str,
    zone_id: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Create a DNSSEC cryptokey. Requires DNSSEC admin privileges."""
    from powerdnsadmin.models.setting import Setting

    if (apikey.role.name not in ("Administrator", "Operator")
            and Setting().get("dnssec_admins_only")):
        raise HTTPException(
            status_code=403,
            detail="API key does not have enough privileges to configure DNSSEC",
        )

    return await forward_to_pdns(request)


@router.api_route(
    "/servers/{server_id}/zones/{zone_id}/cryptokeys/{cryptokey_id}",
    methods=["GET", "PUT", "DELETE"],
)
async def cryptokey_detail(
    server_id: str,
    zone_id: str,
    cryptokey_id: str,
    request: Request,
    apikey=Depends(apikey_can_configure_dnssec),
):
    """Get/update/delete a specific DNSSEC cryptokey."""
    # Also need domain access check
    if apikey.role.name not in ("Administrator", "Operator"):
        domain_names = [item.name for item in apikey.domains]
        accounts_domains = [d.name for a in apikey.accounts for d in a.domains]
        allowed = set(domain_names + accounts_domains)
        if zone_id.rstrip(".") not in allowed:
            raise HTTPException(status_code=403, detail="Zone access not allowed")

    return await forward_to_pdns(request)


# ── Zone subpath forwarding (catch-all, MUST be after specific routes) ─


@router.api_route(
    "/servers/{server_id}/zones/{zone_id}/{subpath:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def zone_subpath_forward(
    server_id: str,
    zone_id: str,
    subpath: str,
    request: Request,
    apikey=Depends(apikey_can_access_domain),
):
    """Forward zone subpath requests to PowerDNS API."""
    return await forward_to_pdns(request)


# ── Server endpoints ─────────────────────────────────────────────────
# NOTE: /servers and /servers/{server_id} are placed here, AFTER all
# zone routes. The catch-all /servers/{server_id}/{subpath:path} route
# is deliberately omitted to avoid swallowing zone routes. Server admin
# sub-paths (config, statistics) are handled by the zone subpath
# forwarder since they go through PowerDNS API anyway. If we need
# server-specific admin routes, they should be added as explicit paths.


@router.get("/servers")
async def list_servers(request: Request, apikey=Depends(get_current_apikey)):
    """List PowerDNS servers."""
    return await forward_to_pdns(request)


@router.get("/servers/{server_id}")
async def get_server(
    server_id: str,
    request: Request,
    apikey=Depends(get_current_apikey),
):
    """Get PowerDNS server configuration."""
    return await forward_to_pdns(request)


# ── Utility endpoints ────────────────────────────────────────────────


@router.get("/sync_domains")
def sync_domains(
    request: Request,
    auth=Depends(get_current_user_or_apikey),
):
    """Synchronize zones from PowerDNS to local database."""
    from powerdnsadmin.models.domain import Domain

    Domain().update()

    return "Finished synchronization in background"


# ── Helpers ──────────────────────────────────────────────────────────


def _validate_rrset_types(body_data: dict):
    """Validate that rrset record types are allowed for User role."""
    from powerdnsadmin.models.setting import Setting

    records_allowed = Setting().get_records_allow_to_edit()
    try:
        for record in body_data.get("rrsets", []):
            if "type" not in record:
                raise HTTPException(
                    status_code=400,
                    detail="Record type not allowed or does not present",
                )
            if record["type"] not in records_allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Record type not allowed: {}".format(record["type"]),
                )
    except (TypeError, KeyError):
        raise


def _validate_rrset_ttl(body_data: dict):
    """Validate that rrset TTLs are allowed for User role."""
    from powerdnsadmin.models.setting import Setting

    if not Setting().get("enforce_api_ttl"):
        return

    allowed_ttls = Setting().get_ttl_options()
    allowed_numeric = [ttl[0] for ttl in allowed_ttls]
    try:
        for record in body_data.get("rrsets", []):
            if "ttl" not in record:
                raise HTTPException(
                    status_code=400,
                    detail="Record TTL not allowed or does not present",
                )
            if record["ttl"] not in allowed_numeric:
                raise HTTPException(
                    status_code=400,
                    detail="Record TTL not allowed: {}".format(record["ttl"]),
                )
    except (TypeError, KeyError):
        raise
