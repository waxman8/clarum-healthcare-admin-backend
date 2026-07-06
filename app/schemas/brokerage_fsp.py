# Auto-generated Pydantic schemas for Brokerage
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class BrokerageBase(BaseModel):
    scheme_id: int
    company_name: str
    fsp_number: str
    contact_person: Optional[str] = None
    email: str
    phone: Optional[str] = None
    physical_address: Optional[str] = None
    fsp_status: str
    fais_category: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None


class BrokerageCreate(BrokerageBase):
    pass


class BrokerageUpdate(BaseModel):
    scheme_id: Optional[int] = None
    company_name: Optional[str] = None
    fsp_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    physical_address: Optional[str] = None
    fsp_status: Optional[str] = None
    fais_category: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class BrokerageRead(BrokerageBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
