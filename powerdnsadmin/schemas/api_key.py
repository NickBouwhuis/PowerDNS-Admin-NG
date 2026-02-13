from typing import Optional, Union
from pydantic import BaseModel

from .role import RoleSchema
from .zone import ZoneSummary
from .account import AccountSummary


class ApiKeyBase(BaseModel):
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    role: Union[str, dict]
    description: Optional[str] = None
    domains: list[Union[str, dict]] = []
    accounts: list[Union[str, dict]] = []


class ApiKeySummary(BaseModel):
    id: int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ApiKeyDetail(BaseModel):
    """Matches the existing ApiKeySchema (lima)."""
    id: int
    role: Optional[RoleSchema] = None
    domains: list[ZoneSummary] = []
    accounts: list[AccountSummary] = []
    description: Optional[str] = None
    key: Optional[str] = None

    model_config = {"from_attributes": True}


class ApiKeyPlain(BaseModel):
    """Matches the existing ApiPlainKeySchema (lima) - includes plain_key."""
    id: int
    role: Optional[RoleSchema] = None
    domains: list[ZoneSummary] = []
    accounts: list[AccountSummary] = []
    description: Optional[str] = None
    plain_key: Optional[str] = None

    model_config = {"from_attributes": True}
