from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from app.schemas.members import DependantResponse


class ClaimLineCreate(BaseModel):
    tariff_code: str
    description: Optional[str] = None
    icd10_code: Optional[str] = None
    quantity: int = 1
    billed_amount: int  # cents


class ClaimCreate(BaseModel):
    scheme_id: int
    member_id: int
    dependant_id: Optional[int] = None
    provider_id: int
    auth_number: Optional[str] = None
    date_of_service_from: date
    date_of_service_to: date
    claim_type: str
    lines: List[ClaimLineCreate] = []


class ClaimAdjudicate(BaseModel):
    approved_lines: List[dict]  # {line_id, approved_amount, rejection_reason_code, rejection_reason_text}


class ClaimOverride(BaseModel):
    reason: str
    override_status: str


class ClaimLineResponse(BaseModel):
    id: int
    claim_id: int
    tariff_code: str
    description: Optional[str] = None
    icd10_code: Optional[str] = None
    quantity: int
    billed_amount: int
    approved_amount: int
    nhrpl_rate: Optional[int] = None
    member_liability: int
    rejection_reason_code: Optional[str] = None
    rejection_reason_text: Optional[str] = None
    is_pmb_line: bool

    model_config = {"from_attributes": True}


class ProviderSummary(BaseModel):
    id: int
    trading_name: str
    practice_number: str

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class ClaimResponse(BaseModel):
    id: int
    claim_number: str
    scheme_id: int
    member_id: int
    member: Optional[MemberSummary] = None
    dependant_id: Optional[int] = None
    dependant: Optional[DependantResponse] = None
    provider_id: int
    provider: Optional[ProviderSummary] = None
    auth_number: Optional[str] = None
    date_of_service_from: date
    date_of_service_to: date
    date_received: date
    claim_type: str
    status: str
    total_billed: int
    total_approved: int
    total_member_liability: int
    total_scheme_liability: int
    is_pmb: bool
    adjudicated_at: Optional[datetime] = None
    created_at: datetime
    lines: List[ClaimLineResponse] = []

    model_config = {"from_attributes": True}


class PaginatedClaimsResponse(BaseModel):
    items: List[ClaimResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RulesEngineResult(BaseModel):
    rule: str
    status: str  # PASS / FAIL / FLAG
    message: str


class AuditTrailEntry(BaseModel):
    id: int
    timestamp: datetime
    action: str
    entity_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None

    model_config = {"from_attributes": True}
