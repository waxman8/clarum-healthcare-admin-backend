from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime


class MemberCreate(BaseModel):
    scheme_id: int
    id_number: str
    first_name: str
    surname: str
    date_of_birth: date
    gender: str
    email: Optional[str] = None
    cell_number: Optional[str] = None
    plan_option_id: int
    join_date: date
    status: str = "pending"


class MemberUpdate(BaseModel):
    first_name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    cell_number: Optional[str] = None
    plan_option_id: Optional[int] = None


class MemberStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


class PlanOptionResponse(BaseModel):
    id: int
    name: str
    code: str
    monthly_premium: int

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: int
    scheme_id: int
    membership_number: str
    id_number: str
    first_name: str
    surname: str
    date_of_birth: date
    gender: str
    email: Optional[str] = None
    cell_number: Optional[str] = None
    plan_option_id: int
    plan_option: Optional[PlanOptionResponse] = None
    status: str
    join_date: date
    termination_date: Optional[date] = None
    waiting_period_end_date: Optional[date] = None
    late_joiner_penalty_pct: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DependantCreate(BaseModel):
    dependant_relationship: str
    id_number: Optional[str] = None
    first_name: str
    surname: str
    date_of_birth: date
    gender: str
    dependant_code: str
    status: str = "active"


class DependantUpdate(BaseModel):
    dependant_relationship: Optional[str] = None
    id_number: Optional[str] = None
    first_name: Optional[str] = None
    surname: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    dependant_code: Optional[str] = None
    status: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class DependantResponse(BaseModel):
    id: int
    member_id: int
    dependant_relationship: str
    id_number: Optional[str] = None
    first_name: str
    surname: str
    date_of_birth: date
    gender: str
    status: str
    dependant_code: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    model_config = {"from_attributes": True}


class BenefitLimitResponse(BaseModel):
    id: int
    plan_option_id: int
    benefit_category: str
    limit_type: str
    limit_value: int
    applied_value: int
    benefit_year: int

    model_config = {"from_attributes": True}


class MemberStatusHistoryResponse(BaseModel):
    id: int
    member_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_at: datetime
    reason: Optional[str] = None

    model_config = {"from_attributes": True}


class MemberSearchRequest(BaseModel):
    query: Optional[str] = None
    status: Optional[str] = None
    plan_option_id: Optional[int] = None
    page: int = 1
    page_size: int = 20


class PaginatedMembersResponse(BaseModel):
    items: List[MemberResponse]
    total: int
    page: int
    page_size: int
    pages: int
