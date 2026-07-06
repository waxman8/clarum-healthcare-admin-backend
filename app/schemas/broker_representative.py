# Auto-generated Pydantic schemas for Broker
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class BrokerBase(BaseModel):
    scheme_id: int
    brokerage_id: Optional[int] = None
    full_name: str
    id_number: Optional[str] = None
    cms_accreditation_number: Optional[str] = None
    fais_representative_number: Optional[str] = None
    email: str
    cell_number: Optional[str] = None
    accreditation_status: str
    accreditation_expiry: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None


class BrokerCreate(BrokerBase):
    pass


class BrokerUpdate(BaseModel):
    scheme_id: Optional[int] = None
    brokerage_id: Optional[int] = None
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    cms_accreditation_number: Optional[str] = None
    fais_representative_number: Optional[str] = None
    email: Optional[str] = None
    cell_number: Optional[str] = None
    accreditation_status: Optional[str] = None
    accreditation_expiry: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class BrokerRead(BrokerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
