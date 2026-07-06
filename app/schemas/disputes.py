from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class DisputeCreate(BaseModel):
    member_id: int
    claim_id: Optional[int] = None
    dispute_type: str  # CLAIM_REJECTION | BENEFIT_LIMIT | AUTHORISATION | CONTRIBUTION | OTHER
    description: str
    date_received: Optional[date] = None  # defaults to today if omitted


class DisputeResolve(BaseModel):
    status: str  # UPHELD | DISMISSED | ESCALATED_TO_CMS
    resolution: str
    cms_reference: Optional[str] = None


class MemberSummary(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class DisputeResponse(BaseModel):
    id: int
    scheme_id: int
    dispute_number: str
    member_id: int
    member: Optional[MemberSummary] = None
    claim_id: Optional[int] = None
    dispute_type: str
    description: str
    status: str
    date_received: date
    member_deadline: date
    admin_deadline: date
    resolution: Optional[str] = None
    escalated_to_cms: bool
    cms_reference: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedDisputesResponse(BaseModel):
    items: List[DisputeResponse]
    total: int
    page: int
    page_size: int
    pages: int
