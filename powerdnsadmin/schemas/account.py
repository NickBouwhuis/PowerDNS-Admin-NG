from typing import Optional
from pydantic import BaseModel

from .zone import ZoneSummary


class AccountBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact: Optional[str] = None
    mail: Optional[str] = None

    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    name: str
    description: Optional[str] = None
    contact: Optional[str] = None
    mail: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contact: Optional[str] = None
    mail: Optional[str] = None


class AccountSummary(BaseModel):
    """Matches the existing AccountSummarySchema (lima)."""
    id: int
    name: str
    domains: list[ZoneSummary] = []

    model_config = {"from_attributes": True}


class ApiKeySummaryRef(BaseModel):
    """Minimal API key reference to avoid circular imports."""
    id: int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class AccountDetail(BaseModel):
    """Matches the existing AccountSchema (lima)."""
    id: int
    name: str
    description: Optional[str] = None
    contact: Optional[str] = None
    mail: Optional[str] = None
    domains: list[ZoneSummary] = []
    apikeys: list[ApiKeySummaryRef] = []

    model_config = {"from_attributes": True}
