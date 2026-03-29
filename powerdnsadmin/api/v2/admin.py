"""
API v2 admin endpoints — session-based admin management for the SPA.

Provides user, account, API key, and template management.
All endpoints require Administrator or Operator role via session auth.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-v2"])


# ---------------------------------------------------------------------------
# Helpers (shared with zones.py)
# ---------------------------------------------------------------------------

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


# ===================================================================
# USER MANAGEMENT
# ===================================================================

class UserCreateRequest(BaseModel):
    username: str
    password: str | None = None
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    role_name: str = "User"


class UserUpdateRequest(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    password: str | None = None
    role_name: str | None = None
    otp_secret: str | None = None


@router.get("/users")
async def list_users(request: Request):
    """List all users."""
    from powerdnsadmin.models.user import User

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    users = User.query.order_by(User.username).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "firstname": u.firstname or "",
            "lastname": u.lastname or "",
            "email": u.email or "",
            "role": u.role.name if u.role else None,
            "otp_enabled": bool(u.otp_secret),
        }
        for u in users
    ]


@router.get("/users/{username}")
async def get_user(username: str, request: Request):
    """Get user details by username."""
    from powerdnsadmin.models.user import User

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    target = User.query.filter(User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    accounts = target.get_accounts() if hasattr(target, "get_accounts") else []

    return {
        "id": target.id,
        "username": target.username,
        "firstname": target.firstname or "",
        "lastname": target.lastname or "",
        "email": target.email or "",
        "role": target.role.name if target.role else None,
        "otp_enabled": bool(target.otp_secret),
        "accounts": [
            {"id": a.id, "name": a.name}
            for a in accounts
        ],
    }


@router.post("/users", status_code=201)
async def create_user(request: Request, body: UserCreateRequest):
    """Create a new user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.role import Role

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    role = Role.query.filter(Role.name == body.role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role_name}")

    new_user = User(
        username=body.username,
        firstname=body.firstname,
        lastname=body.lastname,
        email=body.email,
        role_id=role.id,
        plain_text_password=body.password,
    )
    result = new_user.create_local_user()
    if result.get("status") is False:
        raise HTTPException(status_code=400, detail=result.get("msg", "User creation failed"))

    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": body.role_name,
        "message": "User created",
    }


@router.put("/users/{user_id}")
async def update_user(user_id: int, request: Request, body: UserUpdateRequest):
    """Update user details."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.role import Role
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    target = db.session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if body.firstname is not None:
        target.firstname = body.firstname
    if body.lastname is not None:
        target.lastname = body.lastname
    if body.email is not None:
        target.email = body.email
    if body.password is not None:
        target.password = target.get_hashed_password(body.password)
    if body.role_name is not None:
        role = Role.query.filter(Role.name == body.role_name).first()
        if not role:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role_name}")
        target.role_id = role.id
    if body.otp_secret is not None:
        target.otp_secret = body.otp_secret if body.otp_secret else ""

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "User updated"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, request: Request):
    """Delete a user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    target = db.session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = target.delete()
    if not result:
        raise HTTPException(status_code=400, detail="Failed to delete user")

    return {"status": "ok", "message": "User deleted"}


# ===================================================================
# ACCOUNT MANAGEMENT
# ===================================================================

class AccountCreateRequest(BaseModel):
    name: str
    description: str = ""
    contact: str = ""
    mail: str = ""


class AccountUpdateRequest(BaseModel):
    description: str | None = None
    contact: str | None = None
    mail: str | None = None


@router.get("/accounts")
async def list_accounts(request: Request):
    """List all accounts."""
    from powerdnsadmin.models.account import Account

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    accounts = Account.query.order_by(Account.name).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description or "",
            "contact": a.contact or "",
            "mail": a.mail or "",
            "domain_count": len(a.domains) if a.domains else 0,
            "user_count": len(a.get_user()) if hasattr(a, "get_user") else 0,
        }
        for a in accounts
    ]


@router.get("/accounts/{account_id}")
async def get_account(account_id: int, request: Request):
    """Get account details."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    account = db.session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    user_ids = account.get_user() if hasattr(account, "get_user") else []
    members = []
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        members = [{"id": u.id, "username": u.username} for u in users]

    domains = [{"id": d.id, "name": d.name} for d in (account.domains or [])]

    return {
        "id": account.id,
        "name": account.name,
        "description": account.description or "",
        "contact": account.contact or "",
        "mail": account.mail or "",
        "members": members,
        "domains": domains,
    }


@router.post("/accounts", status_code=201)
async def create_account(request: Request, body: AccountCreateRequest):
    """Create a new account."""
    from powerdnsadmin.models.account import Account

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    account = Account(
        name=body.name,
        description=body.description,
        contact=body.contact,
        mail=body.mail,
    )
    result = account.create_account()
    if result.get("status") is False:
        raise HTTPException(status_code=400, detail=result.get("msg", "Account creation failed"))

    return {
        "id": account.id,
        "name": account.name,
        "message": "Account created",
    }


@router.put("/accounts/{account_id}")
async def update_account(account_id: int, request: Request, body: AccountUpdateRequest):
    """Update account details."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    account = db.session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.description is not None:
        account.description = body.description
    if body.contact is not None:
        account.contact = body.contact
    if body.mail is not None:
        account.mail = body.mail

    result = account.update_account()
    if result.get("status") is False:
        raise HTTPException(status_code=400, detail=result.get("msg", "Account update failed"))

    return {"status": "ok", "message": "Account updated"}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, request: Request):
    """Delete an account."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    account = db.session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result = account.delete_account()
    if not result:
        raise HTTPException(status_code=400, detail="Failed to delete account")

    return {"status": "ok", "message": "Account deleted"}


@router.put("/accounts/{account_id}/members")
async def update_account_members(account_id: int, request: Request):
    """Update account member list."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    account = db.session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    body = await request.json()
    user_ids = body.get("user_ids", [])

    account.grant_privileges(user_ids)

    return {"status": "ok", "message": "Account members updated"}


# ===================================================================
# API KEY MANAGEMENT
# ===================================================================

class ApiKeyCreateRequest(BaseModel):
    description: str = ""
    role_name: str = "User"
    domain_names: list[str] = []
    account_names: list[str] = []


class ApiKeyUpdateRequest(BaseModel):
    description: str | None = None
    role_name: str | None = None
    domain_names: list[str] | None = None
    account_names: list[str] | None = None


@router.get("/apikeys")
async def list_apikeys(request: Request):
    """List all API keys."""
    from powerdnsadmin.models.api_key import ApiKey

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    keys = ApiKey.query.all()
    return [
        {
            "id": k.id,
            "description": k.description or "",
            "role": k.role.name if k.role else None,
            "domains": [{"id": d.id, "name": d.name} for d in (k.domains or [])],
            "accounts": [{"id": a.id, "name": a.name} for a in (k.accounts or [])],
        }
        for k in keys
    ]


@router.get("/apikeys/{key_id}")
async def get_apikey(key_id: int, request: Request):
    """Get API key details."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    key = db.session.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    return {
        "id": key.id,
        "description": key.description or "",
        "role": key.role.name if key.role else None,
        "domains": [{"id": d.id, "name": d.name} for d in (key.domains or [])],
        "accounts": [{"id": a.id, "name": a.name} for a in (key.accounts or [])],
    }


@router.post("/apikeys", status_code=201)
async def create_apikey(request: Request, body: ApiKeyCreateRequest):
    """Create a new API key. Returns the plain key (shown once only)."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.account import Account

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    # Resolve domains
    domains = []
    for name in body.domain_names:
        d = Domain.query.filter(Domain.name == name).first()
        if d:
            domains.append(d)

    # Resolve accounts
    accounts = []
    for name in body.account_names:
        a = Account.query.filter(Account.name == name).first()
        if a:
            accounts.append(a)

    try:
        key = ApiKey(description=body.description)
        key.create(
            role_name=body.role_name,
            domains=domains,
            accounts=accounts,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": key.id,
        "description": key.description or "",
        "role": key.role.name if key.role else None,
        "plain_key": key.plain_key if hasattr(key, "plain_key") else None,
        "domains": [{"id": d.id, "name": d.name} for d in (key.domains or [])],
        "accounts": [{"id": a.id, "name": a.name} for a in (key.accounts or [])],
    }


@router.put("/apikeys/{key_id}")
async def update_apikey(key_id: int, request: Request, body: ApiKeyUpdateRequest):
    """Update an API key."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    key = db.session.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Resolve domains if provided
    domains = None
    if body.domain_names is not None:
        domains = []
        for name in body.domain_names:
            d = Domain.query.filter(Domain.name == name).first()
            if d:
                domains.append(d)

    # Resolve accounts if provided
    accounts = None
    if body.account_names is not None:
        accounts = []
        for name in body.account_names:
            a = Account.query.filter(Account.name == name).first()
            if a:
                accounts.append(a)

    try:
        key.update(
            role_name=body.role_name or (key.role.name if key.role else None),
            description=body.description if body.description is not None else key.description,
            domains=domains if domains is not None else key.domains,
            accounts=accounts if accounts is not None else key.accounts,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "API key updated"}


@router.delete("/apikeys/{key_id}")
async def delete_apikey(key_id: int, request: Request):
    """Delete an API key."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    key = db.session.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    try:
        key.delete()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "API key deleted"}


# ===================================================================
# TEMPLATE MANAGEMENT
# ===================================================================

class TemplateCreateRequest(BaseModel):
    name: str
    description: str = ""


class TemplateRecordItem(BaseModel):
    name: str
    type: str
    ttl: int = 3600
    data: str
    comment: str = ""
    status: bool = True


class TemplateFromZoneRequest(BaseModel):
    name: str
    description: str = ""
    zone_name: str


@router.get("/templates")
async def list_templates(request: Request):
    """List all domain templates."""
    from powerdnsadmin.models.domain_template import DomainTemplate

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    templates = DomainTemplate.query.order_by(DomainTemplate.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "record_count": len(t.records) if t.records else 0,
        }
        for t in templates
    ]


@router.get("/templates/{template_id}")
async def get_template(template_id: int, request: Request):
    """Get template with its records."""
    from powerdnsadmin.models.domain_template import DomainTemplate
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    template = db.session.get(DomainTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": template.id,
        "name": template.name,
        "description": template.description or "",
        "records": [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "ttl": r.ttl,
                "data": r.data,
                "comment": r.comment or "",
                "status": r.status,
            }
            for r in (template.records or [])
        ],
    }


@router.post("/templates", status_code=201)
async def create_template(request: Request, body: TemplateCreateRequest):
    """Create a new domain template."""
    from powerdnsadmin.models.domain_template import DomainTemplate

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    template = DomainTemplate(
        name=body.name,
        description=body.description,
    )
    result = template.create()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "Template creation failed"))

    return {
        "id": template.id,
        "name": template.name,
        "message": "Template created",
    }


@router.put("/templates/{template_id}")
async def update_template(template_id: int, request: Request):
    """Update template metadata and/or records."""
    from powerdnsadmin.models.domain_template import DomainTemplate
    from powerdnsadmin.models.domain_template_record import DomainTemplateRecord
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    template = db.session.get(DomainTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    body = await request.json()

    # Update metadata
    if "description" in body:
        template.description = body["description"]

    # Update records if provided
    if "records" in body:
        records = []
        for r in body["records"]:
            records.append(
                DomainTemplateRecord(
                    name=r["name"],
                    type=r["type"],
                    ttl=r.get("ttl", 3600),
                    data=r["data"],
                    comment=r.get("comment", ""),
                    status=r.get("status", True),
                    template_id=template_id,
                )
            )
        result = template.replace_records(records)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg", "Failed to update records"))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "Template updated"}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, request: Request):
    """Delete a domain template."""
    from powerdnsadmin.models.domain_template import DomainTemplate
    from powerdnsadmin.models.base import db

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    template = db.session.get(DomainTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    result = template.delete_template()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "Template deletion failed"))

    return {"status": "ok", "message": "Template deleted"}


@router.post("/templates/from-zone", status_code=201)
async def create_template_from_zone(request: Request, body: TemplateFromZoneRequest):
    """Create a template from an existing zone's records."""
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain_template import DomainTemplate
    from powerdnsadmin.models.domain_template_record import DomainTemplateRecord
    from powerdnsadmin.models.record import Record

    user = _get_authenticated_user(request)
    _require_admin_or_operator(user)

    # Verify zone exists
    domain = Domain.query.filter(Domain.name == body.zone_name).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Create template
    template = DomainTemplate(
        name=body.name,
        description=body.description or f"Created from zone {body.zone_name}",
    )
    result = template.create()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("msg", "Template creation failed"))

    # Fetch zone records
    try:
        rrsets = Record().get_rrsets(body.zone_name)
    except Exception as e:
        logger.error("Cannot fetch records for %s: %s", body.zone_name, e)
        raise HTTPException(status_code=502, detail="Failed to fetch zone records")

    # Convert rrsets to template records
    records = []
    for rrset in rrsets:
        r_name = rrset["name"].rstrip(".")
        # Make name relative to zone
        if r_name == body.zone_name:
            relative_name = body.zone_name
        elif r_name.endswith("." + body.zone_name):
            relative_name = r_name[: -(len(body.zone_name) + 1)]
        else:
            relative_name = r_name

        for idx, record in enumerate(rrset["records"]):
            comment = ""
            if idx < len(rrset.get("comments", [])):
                comment = rrset["comments"][idx].get("content", "")

            records.append(
                DomainTemplateRecord(
                    name=relative_name,
                    type=rrset["type"],
                    ttl=rrset["ttl"],
                    data=record["content"],
                    comment=comment,
                    status=not record.get("disabled", False),
                    template_id=template.id,
                )
            )

    if records:
        template.replace_records(records)

    return {
        "id": template.id,
        "name": template.name,
        "record_count": len(records),
        "message": f"Template created from zone {body.zone_name}",
    }
