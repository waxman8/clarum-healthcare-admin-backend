# Auto-generated Pydantic schemas for StatutoryActuary
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class StatutoryActuaryBase(BaseModel):
    scheme_id: int
    full_name: str
    firm_name: Optional[str] = None
    assa_fellowship_number: Optional[str] = None
    email: str
    phone: Optional[str] = None
    appointment_date: Optional[date] = None
    term_end_date: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None


class StatutoryActuaryCreate(StatutoryActuaryBase):
    pass


class StatutoryActuaryUpdate(BaseModel):
    scheme_id: Optional[int] = None
    full_name: Optional[str] = None
    firm_name: Optional[str] = None
    assa_fellowship_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    appointment_date: Optional[date] = None
    term_end_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class StatutoryActuaryRead(StatutoryActuaryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
