from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.members import DependantResponse


class AuthorisationLineCreate(BaseModel):
    tariff_code: str
    description: Optional[str] = None
    quantity_requested: int = 1


class AuthorisationCreate(BaseModel):
    member_id: int
    dependant_id: Optional[int] = None
    requesting_provider_id: int
    icd10_codes: List[str] = []
    procedure_codes: List[str] = []
    auth_type: str
    clinical_notes: Optional[str] = None
    lines: List[AuthorisationLineCreate] = []


class AuthorisationApprove(BaseModel):
    approved_days: Optional[int] = None
    clinical_notes: Optional[str] = None
    approved_lines: Optional[List[dict]] = None


class AuthorisationDecline(BaseModel):
    reason: str
    clinical_notes: Optional[str] = None


class AuthorisationLineResponse(BaseModel):
    id: int
    auth_id: int
    tariff_code: str
    description: Optional[str] = None
    quantity_requested: int
    quantity_approved: Optional[int] = None
    reason_declined: Optional[str] = None

    model_config = {"from_attributes": True}


class ProviderSummary(BaseModel):
    id: int
    trading_name: str
    practice_number: str
    provider_type: Optional[str] = None

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class AuthorisationResponse(BaseModel):
    id: int
    auth_number: str
    member_id: int
    member: Optional[MemberSummary] = None
    dependant_id: Optional[int] = None
    dependant: Optional[DependantResponse] = None
    requesting_provider_id: int
    requesting_provider: Optional[ProviderSummary] = None
    icd10_codes: Optional[str] = None
    procedure_codes: Optional[str] = None
    auth_type: str
    status: str
    approved_days: Optional[int] = None
    clinical_notes: Optional[str] = None
    created_at: datetime
    lines: List[AuthorisationLineResponse] = []

    model_config = {"from_attributes": True}


class PaginatedAuthorisationsResponse(BaseModel):
    items: List[AuthorisationResponse]
    total: int
    page: int
    page_size: int
    pages: int
