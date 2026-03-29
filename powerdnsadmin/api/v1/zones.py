"""Zone management endpoints (Basic auth / pdnsadmin path).

These endpoints use HTTP Basic auth and are accessed at
/api/v1/pdnsadmin/zones. They correspond to the Flask endpoints:
  - POST   /api/v1/pdnsadmin/zones
  - GET    /api/v1/pdnsadmin/zones
  - DELETE /api/v1/pdnsadmin/zones/{domain_name}
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..deps import (
    get_current_user,
    user_can_create_domain,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["zones"])


def _get_user_domains(db, user, Domain, DomainUser, Account, AccountUser):
    """Get domains accessible to a non-admin user (via direct grant or account)."""
    return (
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
        .all()
    )


@router.get("/pdnsadmin/zones")
def list_zones(request: Request, user=Depends(get_current_user)):
    """List zones accessible to the authenticated user."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain import DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.base import db
    from powerdnsadmin.schemas import ZoneSummary

    if user.role.name in ("Administrator", "Operator"):
        domains = Domain.query.all()
    else:
        domains = _get_user_domains(
            db, user, Domain, DomainUser, Account, AccountUser
        )

    domains = domains or []
    return [ZoneSummary.model_validate(d).model_dump() for d in domains]


@router.post("/pdnsadmin/zones", status_code=201)
def create_zone(request: Request, user=Depends(user_can_create_domain)):
    """Create a new zone via PowerDNS API."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.services.pdns_client import PowerDNSClient
    from powerdnsadmin.lib import utils

    try:
        body = json.loads(request._body) if hasattr(request, '_body') else {}
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    setting = Setting()
    pdns_api_url = setting.get("pdns_api_url")
    pdns_api_key = setting.get("pdns_api_key")
    pdns_version = setting.get("pdns_version")
    api_uri_with_prefix = utils.pdns_api_extended_uri(pdns_version)
    api_full_uri = api_uri_with_prefix + "/servers/localhost/zones"

    headers = {
        "X-API-Key": pdns_api_key,
        "Content-Type": "application/json",
    }

    try:
        import requests as http_requests
        from urllib.parse import urljoin

        resp = utils.fetch_remote(
            urljoin(pdns_api_url, api_full_uri),
            method="POST",
            data=body,
            headers=headers,
            accept="application/json; q=1",
            verify=setting.get("verify_ssl_connections"),
        )
    except Exception as e:
        logger.error("Cannot create zone. Error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create zone")

    if resp.status_code == 201:
        domain = Domain()
        domain.update()
        domain_id = domain.get_id_by_name(body["name"].rstrip("."))

        history = History(
            msg="Add zone {}".format(body["name"].rstrip(".")),
            detail=json.dumps(body),
            created_by=user.username,
            domain_id=domain_id,
        )
        history.add()

        if user.role.name not in ("Administrator", "Operator"):
            domain = Domain(name=body["name"].rstrip("."))
            domain.update()
            domain.grant_privileges([user.id])

    if resp.status_code == 409:
        raise HTTPException(status_code=409, detail="Zone already exists")

    return JSONResponse(
        content=json.loads(resp.content) if resp.content else {},
        status_code=resp.status_code,
    )


@router.delete("/pdnsadmin/zones/{domain_name}", status_code=204)
def delete_zone(
    domain_name: str,
    request: Request,
    user=Depends(user_can_create_domain),
):
    """Delete a zone via PowerDNS API."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain import DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.base import db
    from powerdnsadmin.lib import utils

    domain = Domain.query.filter(Domain.name == domain_name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Access control for non-admin users
    if user.role.name not in ("Administrator", "Operator"):
        user_domains = _get_user_domains(
            db, user, Domain, DomainUser, Account, AccountUser
        )
        user_domain_names = [d.name for d in user_domains]
        if domain_name not in user_domain_names:
            raise HTTPException(
                status_code=403, detail="Zone access not allowed"
            )

    setting = Setting()
    pdns_api_url = setting.get("pdns_api_url")
    pdns_api_key = setting.get("pdns_api_key")
    pdns_version = setting.get("pdns_version")
    api_uri_with_prefix = utils.pdns_api_extended_uri(pdns_version)
    api_full_uri = api_uri_with_prefix + "/servers/localhost/zones/" + domain_name

    headers = {"X-API-Key": pdns_api_key}

    try:
        from urllib.parse import urljoin

        resp = utils.fetch_remote(
            urljoin(pdns_api_url, api_full_uri),
            method="DELETE",
            headers=headers,
            accept="application/json; q=1",
            verify=setting.get("verify_ssl_connections"),
        )

        if resp.status_code == 204:
            domain_obj = Domain()
            domain_id = domain_obj.get_id_by_name(domain_name)
            domain_obj.update()

            history = History(
                msg="Delete zone {}".format(
                    utils.pretty_domain_name(domain_name)
                ),
                detail="",
                created_by=user.username,
                domain_id=domain_id,
            )
            history.add()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete zone")

    if resp.status_code != 204:
        return JSONResponse(
            content=json.loads(resp.content) if resp.content else {},
            status_code=resp.status_code,
        )

    return None
