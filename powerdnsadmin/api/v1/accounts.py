"""Account management endpoints (Basic auth / pdnsadmin path).

Corresponds to Flask endpoints:
  - GET    /api/v1/pdnsadmin/accounts[/{account_name}]
  - POST   /api/v1/pdnsadmin/accounts
  - PUT    /api/v1/pdnsadmin/accounts/{account_id}
  - DELETE /api/v1/pdnsadmin/accounts/{account_id}
  - GET    /api/v1/pdnsadmin/accounts/{account_id}/users
  - PUT    /api/v1/pdnsadmin/accounts/{account_id}/users/{user_id}
  - DELETE /api/v1/pdnsadmin/accounts/{account_id}/users/{user_id}
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import _get_flask_app, require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["accounts"])


@router.get("/pdnsadmin/accounts")
def list_accounts(
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """List all accounts."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.schemas import AccountDetail

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        accounts = Account.query.all() or []
        return [AccountDetail.model_validate(a).model_dump() for a in accounts]


@router.get("/pdnsadmin/accounts/{account_name}")
def get_account(
    account_name: str,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Get a specific account by name."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.schemas import AccountDetail

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        account = Account.query.filter(Account.name == account_name).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return AccountDetail.model_validate(account).model_dump()


@router.post("/pdnsadmin/accounts", status_code=201)
def create_account(
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Create a new account."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.history import History
    from powerdnsadmin.schemas import AccountDetail

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        data = _get_json_body(request)
        name = data.get("name")
        description = data.get("description")
        contact = data.get("contact")
        mail = data.get("mail")

        if not name:
            raise HTTPException(
                status_code=400, detail="Account name missing"
            )

        sanitized_name = Account.sanitize_name(name)
        existing = Account.query.filter(Account.name == sanitized_name).all()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Account {} would be translated to {} which already exists".format(
                    name, sanitized_name
                ),
            )

        account = Account(
            name=name,
            description=description,
            contact=contact,
            mail=mail,
        )

        try:
            result = account.create_account()
        except Exception as e:
            logger.error("Error: %s", e)
            raise HTTPException(
                status_code=500, detail="Account create failed"
            )

        if not result["status"]:
            raise HTTPException(status_code=500, detail=result["msg"])

        History(
            msg="Create account {}".format(account.name),
            created_by=user.username,
        ).add()

        return AccountDetail.model_validate(account).model_dump()


@router.put("/pdnsadmin/accounts/{account_id}", status_code=204)
def update_account(
    account_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Update an existing account."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.history import History

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        data = _get_json_body(request)
        name = data.get("name")
        description = data.get("description")
        contact = data.get("contact")
        mail = data.get("mail")

        account = Account.query.get(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if name and Account.sanitize_name(name) != account.name:
            raise HTTPException(
                status_code=500, detail="Account name is immutable"
            )

        if description is not None:
            account.description = description
        if contact is not None:
            account.contact = contact
        if mail is not None:
            account.mail = mail

        result = account.update_account()
        if not result["status"]:
            raise HTTPException(status_code=500, detail=result["msg"])

        History(
            msg="Update account {}".format(account.name),
            created_by=user.username,
        ).add()

    return None


@router.delete("/pdnsadmin/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Delete an account."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.history import History

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        accounts = Account.query.filter(Account.id == account_id).all()
        if len(accounts) != 1:
            raise HTTPException(status_code=404, detail="Account not found")

        account = accounts[0]

        # Remove account association from domains first
        if account.domains:
            for domain in account.domains:
                Domain(name=domain.name).assoc_account(None, update=False)
            Domain().update()

        result = account.delete_account()
        if not result:
            raise HTTPException(
                status_code=500, detail="Delete of account failed"
            )

        History(
            msg="Delete account {}".format(account.name),
            created_by=user.username,
        ).add()

    return None


# ── Account-User association endpoints ───────────────────────────────


@router.get("/pdnsadmin/accounts/{account_id}/users")
def list_account_users(
    account_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """List users assigned to an account."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.schemas import UserSummary

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        account = Account.query.get(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        users = (
            User.query.join(AccountUser)
            .filter(AccountUser.account_id == account_id)
            .all()
        )
        return [UserSummary.model_validate(u).model_dump() for u in users]


@router.put(
    "/pdnsadmin/accounts/{account_id}/users/{user_id}", status_code=204
)
def add_account_user(
    account_id: int,
    user_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Add a user to an account."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.history import History

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        account = Account.query.get(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        target_user = User.query.get(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        if not account.add_user(target_user):
            raise HTTPException(
                status_code=500,
                detail="Cannot add user {} to {}".format(
                    target_user.username, account.name
                ),
            )

        History(
            msg="Add {} user privileges on {}".format(
                target_user.username, account.name
            ),
            created_by=user.username,
        ).add()

    return None


@router.delete(
    "/pdnsadmin/accounts/{account_id}/users/{user_id}", status_code=204
)
def remove_account_user(
    account_id: int,
    user_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Remove a user from an account."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.history import History

    flask_app = _get_flask_app(request)
    with flask_app.app_context():
        account = Account.query.get(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        target_user = User.query.get(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify user is associated
        assoc = (
            User.query.join(AccountUser)
            .filter(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
            .all()
        )
        if not assoc:
            raise HTTPException(
                status_code=404, detail="User not in account"
            )

        if not account.remove_user(target_user):
            raise HTTPException(
                status_code=500,
                detail="Cannot remove user {} from {}".format(
                    target_user.username, account.name
                ),
            )

        History(
            msg="Revoke {} user privileges on {}".format(
                target_user.username, account.name
            ),
            created_by=user.username,
        ).add()

    return None


def _get_json_body(request: Request) -> dict:
    """Extract JSON body from request (sync helper)."""
    if hasattr(request, "_body") and request._body:
        return json.loads(request._body)
    return {}
