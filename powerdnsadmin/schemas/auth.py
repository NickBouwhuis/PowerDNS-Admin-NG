from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    otp_token: Optional[str] = None
    auth_method: str = "LOCAL"
