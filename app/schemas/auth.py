from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str
    scheme_id: Optional[int] = None


class SchemeOption(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class SchemePickerResponse(BaseModel):
    requires_scheme_selection: bool = True
    schemes: List[SchemeOption]
    pre_auth_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    scheme_id: Optional[int] = None
    scheme_name: Optional[str] = None
    scheme_code: Optional[str] = None
    created_at: datetime
    available_schemes: List[SchemeOption] = []

    model_config = {"from_attributes": True}


class SchemeCreate(BaseModel):
    name: str
    code: str
    registration_number: str
    cms_accreditation_number: Optional[str] = None


class SchemeResponse(BaseModel):
    id: int
    name: str
    code: str
    registration_number: str
    cms_accreditation_number: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}
