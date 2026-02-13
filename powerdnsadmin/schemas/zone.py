from typing import Optional
from pydantic import BaseModel, field_validator


class ZoneBase(BaseModel):
    name: str
    kind: str = "Native"

    model_config = {"from_attributes": True}


class ZoneCreate(BaseModel):
    name: str
    kind: str = "Native"
    nameservers: list[str] = []
    masters: list[str] = []
    soa_edit_api: str = "DEFAULT"
    account: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {"Native", "Master", "Slave", "Producer", "Consumer"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {allowed}")
        return v

    @field_validator("soa_edit_api")
    @classmethod
    def validate_soa_edit_api(cls, v: str) -> str:
        allowed = {"DEFAULT", "INCREASE", "EPOCH", "OFF"}
        if v not in allowed:
            raise ValueError(f"soa_edit_api must be one of {allowed}")
        return v


class ZoneSummary(BaseModel):
    """Matches the existing DomainSchema (lima) for API compatibility."""
    id: int
    name: str

    model_config = {"from_attributes": True}


class ZoneDetail(BaseModel):
    """Full zone data as returned by PowerDNS API."""
    id: Optional[str] = None
    name: str
    kind: str
    dnssec: bool = False
    account: str = ""
    masters: list[str] = []
    serial: Optional[int] = None
    notified_serial: Optional[int] = None
    last_check: Optional[int] = None
    rrsets: list[dict] = []
