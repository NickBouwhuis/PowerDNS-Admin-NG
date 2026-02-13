from pydantic import BaseModel


class RoleSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
