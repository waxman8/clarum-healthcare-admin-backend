# Auto-generated Pydantic schemas for Trustee
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class TrusteeBase(BaseModel):
    scheme_id: int
    full_name: str
    id_number: Optional[str] = None
    email: str
    cell_number: Optional[str] = None
    role_on_board: str
    appointment_date: date
    term_end_date: Optional[date] = None
    vetting_status: str
    vetting_date: Optional[date] = None
    conflict_disclosed: bool
    notes: Optional[str] = None


class TrusteeCreate(TrusteeBase):
    pass


class TrusteeUpdate(BaseModel):
    scheme_id: Optional[int] = None
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    email: Optional[str] = None
    cell_number: Optional[str] = None
    role_on_board: Optional[str] = None
    appointment_date: Optional[date] = None
    term_end_date: Optional[date] = None
    vetting_status: Optional[str] = None
    vetting_date: Optional[date] = None
    conflict_disclosed: Optional[bool] = None
    notes: Optional[str] = None


class TrusteeRead(TrusteeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
