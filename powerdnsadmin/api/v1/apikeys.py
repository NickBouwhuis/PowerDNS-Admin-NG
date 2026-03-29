"""API key management endpoints (Basic auth / pdnsadmin path).

Corresponds to Flask endpoints:
  - POST   /api/v1/pdnsadmin/apikeys
  - GET    /api/v1/pdnsadmin/apikeys[/{domain_name}]
  - GET    /api/v1/pdnsadmin/apikeys/{apikey_id}  (int)
  - PUT    /api/v1/pdnsadmin/apikeys/{apikey_id}
  - DELETE /api/v1/pdnsadmin/apikeys/{apikey_id}
"""
import logging
from base64 import b64encode

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["apikeys"])


def _get_user_domains(db, user, Domain, DomainUser, Account, AccountUser):
    """Get domains accessible to a non-admin user."""
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


def _get_user_apikeys(db, user, ApiKey, Domain, DomainUser, Account, AccountUser, User, domain_name=None):
    """Get API keys accessible to a non-admin user."""
    query = (
        db.session.query(ApiKey)
        .join(Domain.apikeys)
        .outerjoin(DomainUser, Domain.id == DomainUser.domain_id)
        .outerjoin(Account, Domain.account_id == Account.id)
        .outerjoin(AccountUser, Account.id == AccountUser.account_id)
        .filter(
            db.or_(
                DomainUser.user_id == User.id,
                AccountUser.user_id == User.id,
            )
        )
        .filter(User.id == user.id)
    )
    if domain_name:
        query = query.filter(Domain.name == domain_name)
    return query.all()


@router.post("/pdnsadmin/apikeys", status_code=201)
def create_apikey(
    request: Request,
    user=Depends(get_current_user),
):
    """Create a new API key."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain, DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db
    from powerdnsadmin.schemas import ApiKeyPlain

    data = _get_json_body(request)

    if "role" not in data:
        raise HTTPException(status_code=400, detail="Role is required")

    # Parse role
    if isinstance(data["role"], str):
        role_name = data["role"]
    elif isinstance(data["role"], dict) and "name" in data["role"]:
        role_name = data["role"]["name"]
    else:
        raise HTTPException(status_code=400, detail="Invalid role format")

    # Parse domains
    if "domains" not in data:
        domains = []
    elif not isinstance(data["domains"], list):
        raise HTTPException(status_code=400, detail="Domains must be a list")
    else:
        domains = [
            d["name"] if isinstance(d, dict) else d
            for d in data["domains"]
        ]

    # Parse accounts
    if "accounts" not in data:
        accounts = []
    elif not isinstance(data["accounts"], list):
        raise HTTPException(status_code=400, detail="Accounts must be a list")
    else:
        accounts = [
            a["name"] if isinstance(a, dict) else a
            for a in data["accounts"]
        ]

    description = data.get("description")

    # User role must have zones or accounts
    if role_name == "User" and not domains and not accounts:
        raise HTTPException(
            status_code=400,
            detail="Api key must have zones or accounts or an administrative role",
        )

    domain_obj_list = []
    if role_name == "User" and domains:
        domain_obj_list = Domain.query.filter(Domain.name.in_(domains)).all()
        if not domain_obj_list:
            raise HTTPException(
                status_code=404,
                detail="One of supplied zones does not exist",
            )

    account_obj_list = []
    if role_name == "User" and accounts:
        account_obj_list = Account.query.filter(Account.name.in_(accounts)).all()
        if not account_obj_list:
            raise HTTPException(
                status_code=404,
                detail="One of supplied accounts does not exist",
            )

    # Non-admin restrictions
    if user.role.name not in ("Administrator", "Operator"):
        if role_name != "User":
            raise HTTPException(
                status_code=401,
                detail="User cannot assign other role than User",
            )
        if accounts:
            raise HTTPException(
                status_code=401,
                detail="User cannot assign accounts",
            )

        user_domains = _get_user_domains(
            db, user, Domain, DomainUser, Account, AccountUser
        )
        user_domain_names = {d.name for d in user_domains}
        domain_names = {d.name for d in domain_obj_list}

        if not domain_names.issubset(user_domain_names):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to one of zones",
            )

    apikey = ApiKey(
        desc=description,
        role_name=role_name,
        domains=domain_obj_list,
        accounts=account_obj_list,
    )

    try:
        apikey.create()
    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(
            status_code=500, detail="Api key create failed"
        )

    apikey.plain_key = b64encode(
        apikey.plain_key.encode("utf-8")
    ).decode("utf-8")

    return ApiKeyPlain.model_validate(apikey).model_dump()


@router.get("/pdnsadmin/apikeys")
def list_apikeys(
    request: Request,
    user=Depends(get_current_user),
):
    """List API keys (optionally filtered by domain)."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain, DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db
    from powerdnsadmin.schemas import ApiKeyDetail

    if user.role.name in ("Administrator", "Operator"):
        apikeys = ApiKey.query.all()
    else:
        apikeys = _get_user_apikeys(
            db, user, ApiKey, Domain, DomainUser, Account, AccountUser, User
        )

    return [ApiKeyDetail.model_validate(k).model_dump() for k in apikeys]


@router.get("/pdnsadmin/apikeys/{domain_name}")
def list_apikeys_by_domain(
    domain_name: str,
    request: Request,
    user=Depends(get_current_user),
):
    """List API keys filtered by domain name.

    Note: This handles both GET /pdnsadmin/apikeys/{domain_name} (string)
    and GET /pdnsadmin/apikeys/{apikey_id} (int) by checking if the path
    parameter is numeric.
    """
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain, DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db
    from powerdnsadmin.schemas import ApiKeyDetail

    # If the path parameter is numeric, treat as apikey_id lookup
    try:
        apikey_id = int(domain_name)
        return _get_single_apikey(
            apikey_id, user, db, ApiKey, Domain, DomainUser,
            Account, AccountUser, User
        )
    except ValueError:
        pass

    # Otherwise, treat as domain_name filter
    if user.role.name in ("Administrator", "Operator"):
        apikeys = ApiKey.query.all()
    else:
        apikeys = _get_user_apikeys(
            db, user, ApiKey, Domain, DomainUser,
            Account, AccountUser, User, domain_name=domain_name
        )
        if not apikeys:
            raise HTTPException(
                status_code=403,
                detail="Zone access not allowed {}".format(domain_name),
            )

    return [ApiKeyDetail.model_validate(k).model_dump() for k in apikeys]


def _get_single_apikey(apikey_id, user, db, ApiKey, Domain, DomainUser,
                       Account, AccountUser, User):
    """Get a single API key by ID with access control."""
    from powerdnsadmin.schemas import ApiKeyDetail

    apikey = ApiKey.query.get(apikey_id)
    if not apikey:
        raise HTTPException(status_code=404, detail="API key not found")

    if user.role.name not in ("Administrator", "Operator"):
        user_apikeys = _get_user_apikeys(
            db, user, ApiKey, Domain, DomainUser, Account, AccountUser, User
        )
        if apikey_id not in [k.id for k in user_apikeys]:
            raise HTTPException(
                status_code=403, detail="Zone access not allowed"
            )

    return ApiKeyDetail.model_validate(apikey).model_dump()


@router.put("/pdnsadmin/apikeys/{apikey_id}", status_code=204)
def update_apikey(
    apikey_id: int,
    request: Request,
    user=Depends(get_current_user),
):
    """Update an existing API key."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain, DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    apikey = ApiKey.query.get(apikey_id)
    if not apikey:
        raise HTTPException(status_code=404, detail="API key not found")

    data = _get_json_body(request)
    description = data.get("description")

    # Parse role
    role_name = None
    if "role" in data:
        if isinstance(data["role"], str):
            role_name = data["role"]
        elif isinstance(data["role"], dict) and "name" in data["role"]:
            role_name = data["role"]["name"]
        else:
            raise HTTPException(status_code=400, detail="Invalid role format")
    target_role = role_name or apikey.role.name

    # Parse domains
    domains = None
    if "domains" in data:
        if not isinstance(data["domains"], list):
            raise HTTPException(status_code=400, detail="Domains must be a list")
        domains = [
            d["name"] if isinstance(d, dict) else d
            for d in data["domains"]
        ]

    # Parse accounts
    accounts = None
    if "accounts" in data:
        if not isinstance(data["accounts"], list):
            raise HTTPException(status_code=400, detail="Accounts must be a list")
        accounts = [
            a["name"] if isinstance(a, dict) else a
            for a in data["accounts"]
        ]

    domain_obj_list = None
    account_obj_list = None

    if target_role == "User":
        current_domains = [d.name for d in apikey.domains]
        current_accounts = [a.name for a in apikey.accounts]

        if domains is not None:
            domain_obj_list = Domain.query.filter(Domain.name.in_(domains)).all()
            if len(domain_obj_list) != len(domains):
                raise HTTPException(
                    status_code=404,
                    detail="One of supplied zones does not exist",
                )
            target_domains = domains
        else:
            target_domains = current_domains

        if accounts is not None:
            account_obj_list = Account.query.filter(Account.name.in_(accounts)).all()
            if len(account_obj_list) != len(accounts):
                raise HTTPException(
                    status_code=404,
                    detail="One of supplied accounts does not exist",
                )
            target_accounts = accounts
        else:
            target_accounts = current_accounts

        if not target_domains and not target_accounts:
            raise HTTPException(
                status_code=400,
                detail="Api key must have zones or accounts or an administrative role",
            )

        # Skip update if nothing changed
        if domains is not None and set(domains) == set(current_domains):
            domains = None
        if accounts is not None and set(accounts) == set(current_accounts):
            accounts = None

    # Non-admin restrictions
    if user.role.name not in ("Administrator", "Operator"):
        if role_name and role_name != "User":
            raise HTTPException(
                status_code=401,
                detail="User cannot assign other role than User",
            )
        if accounts:
            raise HTTPException(
                status_code=401,
                detail="User cannot assign accounts",
            )

        user_apikeys = _get_user_apikeys(
            db, user, ApiKey, Domain, DomainUser, Account, AccountUser, User
        )
        if apikey_id not in [k.id for k in user_apikeys]:
            raise HTTPException(
                status_code=403, detail="Zone access not allowed"
            )

        if domain_obj_list is not None:
            user_domains = _get_user_domains(
                db, user, Domain, DomainUser, Account, AccountUser
            )
            user_domain_names = {d.name for d in user_domains}
            if not {d.name for d in domain_obj_list}.issubset(user_domain_names):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to one of zones",
                )

    # Skip no-op updates
    if role_name == apikey.role.name:
        role_name = None
    if description == apikey.description:
        description = None
    if target_role != "User":
        domains, accounts = [], []

    try:
        apikey.update(
            role_name=role_name,
            domains=domains,
            accounts=accounts,
            description=description,
        )
    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(status_code=500, detail="API key update failed")

    return None


@router.delete("/pdnsadmin/apikeys/{apikey_id}", status_code=204)
def delete_apikey(
    apikey_id: int,
    request: Request,
    user=Depends(get_current_user),
):
    """Delete an API key."""
    from powerdnsadmin.models.api_key import ApiKey
    from powerdnsadmin.models.domain import Domain, DomainUser
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.base import db

    apikey = ApiKey.query.get(apikey_id)
    if not apikey:
        raise HTTPException(status_code=404, detail="API key not found")

    if user.role.name not in ("Administrator", "Operator"):
        user_apikeys = _get_user_apikeys(
            db, user, ApiKey, Domain, DomainUser, Account, AccountUser, User
        )
        user_domains = user.get_domain().all()
        user_domain_names = {d.name for d in user_domains}
        apikey_domain_names = {d.name for d in apikey.domains}

        if not apikey_domain_names.issubset(user_domain_names):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to some zones apikey belongs to",
            )

        if apikey_id not in [k.id for k in user_apikeys]:
            raise HTTPException(
                status_code=403, detail="Zone access not allowed"
            )

    try:
        apikey.delete()
    except Exception as e:
        logger.error("Error: %s", e)
        raise HTTPException(
            status_code=500, detail="API key delete failed"
        )

    return None


def _get_json_body(request: Request) -> dict:
    """Extract JSON body from request (sync helper)."""
    import json

    if hasattr(request, "_body") and request._body:
        return json.loads(request._body)
    return {}
