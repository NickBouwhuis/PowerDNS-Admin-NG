from typing import Optional
from pydantic import BaseModel, field_validator


class RecordItem(BaseModel):
    """A single DNS record within an RRSet."""
    content: str
    disabled: bool = False
    set_ptr: bool = False


class CommentItem(BaseModel):
    """A comment on an RRSet."""
    content: str
    account: str = ""
    modified_at: Optional[int] = None


class RRSet(BaseModel):
    """A Resource Record Set as used by PowerDNS API."""
    name: str
    type: str
    ttl: Optional[int] = None
    changetype: str = "REPLACE"
    records: list[RecordItem] = []
    comments: list[CommentItem] = []

    @field_validator("changetype")
    @classmethod
    def validate_changetype(cls, v: str) -> str:
        allowed = {"REPLACE", "DELETE"}
        if v.upper() not in allowed:
            raise ValueError(f"changetype must be one of {allowed}")
        return v.upper()


class RRSetUpdate(BaseModel):
    """Payload for PATCH /zones/{zone_id} to modify records."""
    rrsets: list[RRSet]
