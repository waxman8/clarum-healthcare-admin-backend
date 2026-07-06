# Auto-generated Pydantic schemas for BrokerAppointment
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class BrokerAppointmentBase(BaseModel):
    scheme_id: int
    member_id: int
    broker_id: int
    brokerage_id: Optional[int] = None
    appointment_date: date
    termination_date: Optional[date] = None
    status: str
    termination_reason: Optional[str] = None
    notes: Optional[str] = None


class BrokerAppointmentCreate(BrokerAppointmentBase):
    pass


class BrokerAppointmentUpdate(BaseModel):
    scheme_id: Optional[int] = None
    member_id: Optional[int] = None
    broker_id: Optional[int] = None
    brokerage_id: Optional[int] = None
    appointment_date: Optional[date] = None
    termination_date: Optional[date] = None
    status: Optional[str] = None
    termination_reason: Optional[str] = None
    notes: Optional[str] = None


class BrokerAppointmentRead(BrokerAppointmentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
