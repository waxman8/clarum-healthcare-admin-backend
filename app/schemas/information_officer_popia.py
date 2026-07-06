# Auto-generated Pydantic schemas for InformationOfficer
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class InformationOfficerBase(BaseModel):
    scheme_id: int
    full_name: str
    id_number: Optional[str] = None
    email: str
    cell_number: Optional[str] = None
    appointment_date: Optional[date] = None
    regulator_registration_date: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None


class InformationOfficerCreate(InformationOfficerBase):
    pass


class InformationOfficerUpdate(BaseModel):
    scheme_id: Optional[int] = None
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    email: Optional[str] = None
    cell_number: Optional[str] = None
    appointment_date: Optional[date] = None
    regulator_registration_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class InformationOfficerRead(InformationOfficerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
