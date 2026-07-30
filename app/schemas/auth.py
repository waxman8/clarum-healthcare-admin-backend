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


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class PasswordResetValidateRequest(BaseModel):
    token: str


class PasswordResetValidateResponse(BaseModel):
    valid: bool = True


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
    mfa_enabled: bool = False

    model_config = {"from_attributes": True}


class MfaSetupResponse(BaseModel):
    otpauth_url: str        # otpauth://totp/...
    secret: str             # base32 — shown once, never stored client-side


class MfaVerifyRequest(BaseModel):
    secret: str             # base32 secret returned from setup, passed back by client
    code: str               # 6-digit TOTP


class MfaVerifyResponse(BaseModel):
    enabled: bool
    recovery_codes: List[str]   # 10 plaintext codes — shown once


class MfaDisableRequest(BaseModel):
    password: str
    code: str               # fresh TOTP


class MfaChallengeRequest(BaseModel):
    code: str               # 6-digit TOTP OR recovery code


class MfaChallengeResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MfaRegenerateResponse(BaseModel):
    recovery_codes: List[str]   # 10 new plaintext codes


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    pre_auth_mfa_token: str     # short-lived JWT (10 min), no scheme scope


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
