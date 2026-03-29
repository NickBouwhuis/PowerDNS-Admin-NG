from typing import Optional
from pydantic import BaseModel

from .role import RoleSchema
from .account import AccountSummary


class UserBase(BaseModel):
    username: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    password: Optional[str] = None
    plain_text_password: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    otp_secret: Optional[str] = None
    confirmed: bool = False
    role_name: Optional[str] = None
    role_id: Optional[int] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    plain_text_password: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    otp_secret: Optional[str] = None
    confirmed: Optional[bool] = None
    role_name: Optional[str] = None
    role_id: Optional[int] = None


class UserSummary(BaseModel):
    """Matches the existing UserSchema (lima) for API compatibility."""
    id: int
    username: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    role: Optional[RoleSchema] = None

    model_config = {"from_attributes": True}


class UserDetailed(UserSummary):
    """Matches the existing UserDetailedSchema (lima)."""
    accounts: list[AccountSummary] = []
