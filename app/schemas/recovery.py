from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class RecoveryCaseCreate(BaseModel):
    recovery_type: str
    third_party_name: str = Field(min_length=1, max_length=255)
    third_party_reference: Optional[str] = Field(default=None, max_length=100)
    expected_cents: int = Field(gt=0)


class RecoveryClaimLinkCreate(BaseModel):
    claim_id: int
    allocation_cents: int = Field(gt=0)


class RecoveryTransitionCreate(BaseModel):
    status: str
    receipt_cents: Optional[int] = Field(default=None, gt=0)
    received_on: Optional[date] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class RecoveryClaimLinkRead(BaseModel):
    id: int
    claim_id: int
    allocation_cents: int
    recovered_cents: int

    model_config = {"from_attributes": True}


class RecoveryReceiptRead(BaseModel):
    id: int
    amount_cents: int
    received_on: date
    created_at: datetime

    model_config = {"from_attributes": True}


class RecoveryCaseRead(BaseModel):
    id: int
    recovery_type: str
    status: str
    third_party_name: str
    third_party_reference: Optional[str] = None
    expected_cents: int
    recovered_cents: int
    outstanding_cents: int
    created_at: datetime
    updated_at: datetime
    claim_links: list[RecoveryClaimLinkRead] = []
    receipts: list[RecoveryReceiptRead] = []

    model_config = {"from_attributes": True}


class PaginatedRecoveryCases(BaseModel):
    items: list[RecoveryCaseRead]
    total: int
    page: int
    page_size: int
    pages: int
