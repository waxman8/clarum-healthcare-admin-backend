from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel


class DisputeCreate(BaseModel):
    member_id: int
    claim_id: Optional[int] = None
    dispute_type: str  # CLAIM_REJECTION | BENEFIT_LIMIT | AUTHORISATION | CONTRIBUTION | OTHER
    description: str
    date_received: Optional[date] = None  # defaults to today if omitted


class DisputeTransition(BaseModel):
    to_status: str  # NEW | INVESTIGATING | RESOLVED | REJECTED
    resolution: Optional[str] = None
    reason: Optional[str] = None


class DisputeCommentCreate(BaseModel):
    comment: str


class MemberSummary(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class DisputeResponse(BaseModel):
    id: int
    dispute_number: str
    dispute_type: str
    description: str
    member_id: int
    member: Optional[MemberSummary] = None
    claim_id: Optional[int] = None
    status: str
    status_changed_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    created_at: datetime

    # Legacy fields retained for backward compatibility.
    scheme_id: Optional[int] = None
    date_received: Optional[date] = None
    member_deadline: Optional[date] = None
    admin_deadline: Optional[date] = None
    resolution: Optional[str] = None
    escalated_to_cms: Optional[bool] = None
    cms_reference: Optional[str] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DisputeListResponse(BaseModel):
    items: List[DisputeResponse]
    total: int


class DisputeCommentResponse(BaseModel):
    id: int
    comment: str
    created_at: datetime
    author_name: Optional[str] = None
    created_by_name: Optional[str] = None


class DisputeCommentListResponse(BaseModel):
    items: List[DisputeCommentResponse]
