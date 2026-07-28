from pydantic import BaseModel, EmailStr, computed_field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    scheme_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    scheme_id: Optional[int] = None
    last_login_at: Optional[datetime] = None
    must_reset_password: bool
    created_at: datetime

    @computed_field
    def status(self) -> str:
        return "active" if self.is_active else "deactivated"

    model_config = {
        "from_attributes": True
    }
