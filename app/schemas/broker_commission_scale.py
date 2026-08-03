# Auto-generated Pydantic schemas for BrokerCommissionScale
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class BrokerCommissionScaleBase(BaseModel):
    scheme_id: int
    broker_id: Optional[int] = None
    plan_option_id: Optional[int] = None
    member_type: str
    commission_amount_cents: int
    vat_inclusive: bool
    effective_from: date
    effective_to: Optional[date] = None
    max_pmpm_cents: int
    notes: Optional[str] = None


class BrokerCommissionScaleCreate(BrokerCommissionScaleBase):
    scheme_id: Optional[int] = None


class BrokerCommissionScaleUpdate(BaseModel):
    scheme_id: Optional[int] = None
    broker_id: Optional[int] = None
    plan_option_id: Optional[int] = None
    member_type: Optional[str] = None
    commission_amount_cents: Optional[int] = None
    vat_inclusive: Optional[bool] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    max_pmpm_cents: Optional[int] = None
    notes: Optional[str] = None


class BrokerCommissionScaleRead(BrokerCommissionScaleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrokerCommissionScaleAuditRead(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    timestamp: datetime
    old_value: Optional[str]
    new_value: Optional[str]

    class Config:
        from_attributes = True
