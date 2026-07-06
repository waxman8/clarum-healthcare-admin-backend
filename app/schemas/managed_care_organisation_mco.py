# Auto-generated Pydantic schemas for ManagedCareOrganisation
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class ManagedCareOrganisationBase(BaseModel):
    scheme_id: int
    company_name: str
    accreditation_number: Optional[str] = None
    accreditation_expiry: Optional[date] = None
    contact_person: Optional[str] = None
    email: str
    phone: Optional[str] = None
    programme_types: Optional[str] = None
    accreditation_status: str
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    notes: Optional[str] = None


class ManagedCareOrganisationCreate(ManagedCareOrganisationBase):
    pass


class ManagedCareOrganisationUpdate(BaseModel):
    scheme_id: Optional[int] = None
    company_name: Optional[str] = None
    accreditation_number: Optional[str] = None
    accreditation_expiry: Optional[date] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    programme_types: Optional[str] = None
    accreditation_status: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    notes: Optional[str] = None


class ManagedCareOrganisationRead(ManagedCareOrganisationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
