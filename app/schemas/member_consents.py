# Pydantic schemas for POPIA consent purposes and member consent history
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ConsentPurposeResponse(BaseModel):
    id: int
    code: str
    description: str
    is_active: bool

    model_config = {"from_attributes": True}


class MemberConsentResponse(BaseModel):
    id: int
    member_id: int
    purpose: str
    consented: bool
    version: int
    granted_at: Optional[datetime] = None
    granted_by_user_id: Optional[int] = None
    withdrew_at: Optional[datetime] = None
    withdraw_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrentConsentResponse(BaseModel):
    """Current effective consent state for one purpose (latest version, or none recorded yet)."""
    purpose: str
    description: str
    consented: Optional[bool] = None  # None = not yet recorded
    version: Optional[int] = None
    granted_at: Optional[datetime] = None
    granted_by_user_id: Optional[int] = None
    withdrew_at: Optional[datetime] = None
    withdraw_reason: Optional[str] = None


class ConsentGrantRequest(BaseModel):
    purpose: str


class ConsentWithdrawRequest(BaseModel):
    purpose: str
    withdraw_reason: str
