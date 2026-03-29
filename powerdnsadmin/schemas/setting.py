from typing import Any, Optional
from pydantic import BaseModel


class SettingValue(BaseModel):
    """Response for a single setting."""
    name: str
    value: Any

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    """Request to update a setting."""
    value: Any
