# Auto-generated Pydantic schemas for EmployerGroup
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class EmployerGroupBase(BaseModel):
    scheme_id: int
    company_name: str
    registration_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: str
    phone: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    payroll_reference: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    employee_count: Optional[int] = None
    is_active: bool
    notes: Optional[str] = None


class EmployerGroupCreate(EmployerGroupBase):
    pass


class EmployerGroupUpdate(BaseModel):
    scheme_id: Optional[int] = None
    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    payroll_reference: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    employee_count: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class EmployerGroupRead(EmployerGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
