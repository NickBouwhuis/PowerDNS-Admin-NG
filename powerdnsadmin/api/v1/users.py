"""User management endpoints (Basic auth / pdnsadmin path).

Corresponds to Flask endpoints:
  - GET    /api/v1/pdnsadmin/users[/{username}]
  - POST   /api/v1/pdnsadmin/users
  - PUT    /api/v1/pdnsadmin/users/{user_id}
  - DELETE /api/v1/pdnsadmin/users/{user_id}
"""
import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..deps import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"])


def _get_role_id(role_name, role_id=None):
    """Resolve role ID from name and/or ID."""
    from powerdnsadmin.models.role import Role

    if role_id:
        if role_name:
            role = Role.query.filter(Role.name == role_name).first()
            if not role or role.id != role_id:
                role_id = None
        else:
            role = Role.query.filter(Role.id == role_id).first()
            if not role:
                role_id = None
    else:
        role = Role.query.filter(Role.name == role_name).first()
        role_id = role.id if role else None
    return role_id


@router.get("/pdnsadmin/users")
def list_users(
    request: Request,
    user=Depends(require_role("Administrator", "Operator", allow_self=True)),
):
    """List all users."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.schemas import UserSummary

    users = User.query.all() or []
    return [UserSummary.model_validate(u).model_dump() for u in users]


@router.get("/pdnsadmin/users/{username}")
def get_user(
    username: str,
    request: Request,
    user=Depends(require_role("Administrator", "Operator", allow_self=True)),
):
    """Get a specific user by username."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.schemas import UserDetailed

    target_user = User.query.filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetailed.model_validate(target_user).model_dump()


@router.post("/pdnsadmin/users", status_code=201)
def create_user(
    request: Request,
    user=Depends(require_role("Administrator", "Operator", allow_self=True)),
):
    """Create a new user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.history import History
    from powerdnsadmin.schemas import UserSummary

    try:
        data = _get_json_body(request)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    username = data.get("username")
    password = data.get("password")
    plain_text_password = data.get("plain_text_password")
    firstname = data.get("firstname")
    lastname = data.get("lastname")
    email = data.get("email")
    otp_secret = data.get("otp_secret")
    confirmed = data.get("confirmed")
    role_name = data.get("role_name")
    role_id = data.get("role_id")

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    if not confirmed:
        confirmed = False
    elif confirmed is not True:
        raise HTTPException(status_code=400, detail="Invalid confirmed value")

    if not plain_text_password and not password:
        plain_text_password = "".join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(15)
        )

    if not role_name and not role_id:
        role_name = "User"

    role_id = _get_role_id(role_name, role_id)
    if not role_id:
        raise HTTPException(status_code=400, detail="Invalid role")

    new_user = User(
        username=username,
        password=password,
        plain_text_password=plain_text_password,
        firstname=firstname,
        lastname=lastname,
        role_id=role_id,
        email=email,
        otp_secret=otp_secret,
        confirmed=confirmed,
    )

    try:
        result = new_user.create_local_user()
    except Exception as e:
        logger.error("Create user (%s, %s) error: %s", username, email, e)
        raise HTTPException(status_code=500, detail="User create failed")

    if not result["status"]:
        raise HTTPException(status_code=409, detail=result["msg"])

    History(
        msg="Created user {}".format(new_user.username),
        created_by=user.username,
    ).add()

    return UserSummary.model_validate(new_user).model_dump()


@router.put("/pdnsadmin/users/{user_id}", status_code=204)
def update_user(
    user_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator", allow_self=True)),
):
    """Update an existing user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.history import History

    try:
        data = _get_json_body(request)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    target_user = User.query.get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    username = data.get("username")
    if username and username != target_user.username:
        raise HTTPException(
            status_code=400, detail="Cannot change username"
        )

    password = data.get("password")
    plain_text_password = data.get("plain_text_password")
    firstname = data.get("firstname")
    lastname = data.get("lastname")
    email = data.get("email")
    otp_secret = data.get("otp_secret")
    confirmed = data.get("confirmed")
    role_name = data.get("role_name")
    role_id = data.get("role_id")

    if password is not None:
        target_user.password = password
    target_user.plain_text_password = plain_text_password or ""
    if firstname is not None:
        target_user.firstname = firstname
    if lastname is not None:
        target_user.lastname = lastname
    if email is not None:
        target_user.email = email
    if otp_secret is not None:
        target_user.otp_secret = otp_secret
    if confirmed is not None:
        target_user.confirmed = confirmed
    if role_name is not None:
        target_user.role_id = _get_role_id(role_name, role_id)
    elif role_id is not None:
        target_user.role_id = role_id

    try:
        result = target_user.update_local_user()
    except Exception as e:
        logger.error("Update user (%s, %s) error: %s", username, email, e)
        raise HTTPException(status_code=500, detail="User update failed")

    if not result["status"]:
        if result["msg"].startswith("New email"):
            raise HTTPException(status_code=409, detail=result["msg"])
        raise HTTPException(status_code=500, detail=result["msg"])

    History(
        msg="Updated user {}".format(target_user.username),
        created_by=user.username,
    ).add()

    return None


@router.delete("/pdnsadmin/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    user=Depends(require_role("Administrator", "Operator")),
):
    """Delete a user."""
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.account import Account, AccountUser
    from powerdnsadmin.models.history import History

    target_user = User.query.get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == user.id:
        raise HTTPException(
            status_code=500, detail="Cannot delete self"
        )

    # Remove account associations first
    user_accounts = (
        Account.query.join(AccountUser)
        .join(User)
        .filter(
            AccountUser.user_id == target_user.id,
            AccountUser.account_id == Account.id,
        )
        .all()
    )
    for uc in user_accounts:
        uc.revoke_privileges_by_id(target_user.id)

    result = target_user.delete()
    if not result:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user {}".format(target_user.username),
        )

    History(
        msg="Delete user {}".format(target_user.username),
        created_by=user.username,
    ).add()

    return None


def _get_json_body(request: Request) -> dict:
    """Extract JSON body from request (sync helper)."""
    import json

    if hasattr(request, "_body") and request._body:
        return json.loads(request._body)
    return {}
