# Auto-generated Pydantic schemas for BrokerCommissionScale
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel


class BrokerCommissionScaleBase(BaseModel):
    scheme_id: int
    plan_option_id: Optional[int] = None
    member_type: str
    commission_amount_cents: int
    vat_inclusive: bool
    effective_date: date
    end_date: Optional[date] = None
    regulatory_max_cents: Optional[int] = None
    notes: Optional[str] = None


class BrokerCommissionScaleCreate(BrokerCommissionScaleBase):
    pass


class BrokerCommissionScaleUpdate(BaseModel):
    scheme_id: Optional[int] = None
    plan_option_id: Optional[int] = None
    member_type: Optional[str] = None
    commission_amount_cents: Optional[int] = None
    vat_inclusive: Optional[bool] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    regulatory_max_cents: Optional[int] = None
    notes: Optional[str] = None


class BrokerCommissionScaleRead(BrokerCommissionScaleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
