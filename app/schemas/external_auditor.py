# Auto-generated Pydantic schemas for ExternalAuditor
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class ExternalAuditorBase(BaseModel):
    scheme_id: int
    firm_name: str
    partner_name: Optional[str] = None
    irba_number: Optional[str] = None
    email: str
    phone: Optional[str] = None
    appointment_date: Optional[date] = None
    engagement_end_date: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None


class ExternalAuditorCreate(ExternalAuditorBase):
    pass


class ExternalAuditorUpdate(BaseModel):
    scheme_id: Optional[int] = None
    firm_name: Optional[str] = None
    partner_name: Optional[str] = None
    irba_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    appointment_date: Optional[date] = None
    engagement_end_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ExternalAuditorRead(ExternalAuditorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
