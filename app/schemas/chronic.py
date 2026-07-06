from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from app.schemas.members import DependantResponse


class ChronicRegistrationCreate(BaseModel):
    member_id: int
    dependant_id: Optional[int] = None
    icd10_code_id: int
    notes: Optional[str] = None


class ChronicRegistrationDecision(BaseModel):
    status: str  # APPROVED | DECLINED
    notes: Optional[str] = None
    approved_medicines: Optional[List[int]] = None  # list of nappi_code_ids


class ICD10Summary(BaseModel):
    id: int
    code: str
    description: str
    cdl_condition_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MemberSummary(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class ChronicRegistrationResponse(BaseModel):
    id: int
    scheme_id: int
    member_id: int
    member: Optional[MemberSummary] = None
    dependant_id: Optional[int] = None
    dependant: Optional[DependantResponse] = None
    icd10_code_id: int
    icd10: Optional[ICD10Summary] = None
    status: str
    application_date: date
    decision_date: Optional[date] = None
    expiry_date: Optional[date] = None
    approved_medicines: Optional[str] = None  # raw JSON string
    notes: Optional[str] = None
    is_pmb: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedChronicResponse(BaseModel):
    items: List[ChronicRegistrationResponse]
    total: int
    page: int
    page_size: int
    pages: int
