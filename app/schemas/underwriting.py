from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime


class MemberConditionExclusionCreate(BaseModel):
    icd10_code: str
    condition_name: Optional[str] = None
    is_pmb: bool = False
    exclusion_start_date: date
    exclusion_end_date: date


class MemberConditionExclusionResponse(BaseModel):
    id: int
    underwriting_decision_id: int
    member_id: int
    icd10_code: str
    condition_name: Optional[str] = None
    is_pmb: bool
    exclusion_start_date: date
    exclusion_end_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberSlimResponse(BaseModel):
    id: int
    first_name: str
    surname: str
    membership_number: str

    model_config = {"from_attributes": True}


class UnderwritingDecisionCreate(BaseModel):
    member_id: int
    decision_date: date
    effective_date: date
    decision: str  # "approved" | "conditionally_approved" | "denied" | "referred"
    has_prior_cover: bool = False
    prior_cover_years: Optional[float] = None
    prior_cover_break_days: Optional[int] = None
    prior_cover_proof_type: Optional[str] = None
    prior_cover_schemes_json: Optional[List[Any]] = None
    general_wp_months: Optional[int] = None
    general_wp_end_date: Optional[date] = None
    is_late_joiner: bool = False
    late_joiner_uncovered_years: Optional[int] = None
    late_joiner_penalty_pct: int = 0
    base_monthly_contribution: Optional[int] = None
    total_monthly_contribution: Optional[int] = None
    notes: Optional[str] = None
    condition_exclusions: List[MemberConditionExclusionCreate] = []


class UnderwritingDecisionUpdate(BaseModel):
    notes: Optional[str] = None
    override_reason: Optional[str] = None


class UnderwritingDecisionResponse(BaseModel):
    id: int
    scheme_id: int
    member_id: int
    decision_date: date
    effective_date: date
    decision: str
    status: str
    has_prior_cover: bool
    prior_cover_years: Optional[float] = None
    prior_cover_break_days: Optional[int] = None
    prior_cover_proof_type: Optional[str] = None
    prior_cover_schemes_json: Optional[List[Any]] = None
    general_wp_months: Optional[int] = None
    general_wp_end_date: Optional[date] = None
    is_late_joiner: bool
    late_joiner_uncovered_years: Optional[int] = None
    late_joiner_penalty_pct: int
    base_monthly_contribution: Optional[int] = None
    total_monthly_contribution: Optional[int] = None
    created_by: int
    notes: Optional[str] = None
    override_reason: Optional[str] = None
    engine_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    condition_exclusions: List[MemberConditionExclusionResponse] = []
    member: Optional[MemberSlimResponse] = None

    model_config = {"from_attributes": True}


class UnderwritingPreviewRequest(BaseModel):
    effective_date: date
    has_prior_cover: bool = False
    prior_cover_years: Optional[float] = None
    prior_cover_break_days: Optional[int] = None
    is_late_joiner: bool = False
    late_joiner_uncovered_years: Optional[int] = None
    base_monthly_contribution: Optional[int] = None


class UnderwritingPreviewResponse(BaseModel):
    general_wp_months: int
    general_wp_end_date: Optional[date] = None
    is_late_joiner: bool
    late_joiner_penalty_pct: int
    total_monthly_contribution: Optional[int] = None


class PaginatedUnderwritingResponse(BaseModel):
    items: List[UnderwritingDecisionResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Enrollment Questionnaire
# ---------------------------------------------------------------------------

class DeclaredCondition(BaseModel):
    icd10_code: str
    condition_name: Optional[str] = None


class EnrollmentQuestionnaireCreate(BaseModel):
    member_id: int
    # Gate 1 — reason for joining
    # "new_entrant" | "dependant_becoming_principal" | "transfer" | "other"
    join_reason: str
    # Prior cover
    has_prior_cover: bool = False
    prior_cover_years: Optional[float] = None
    prior_cover_break_days: Optional[int] = None
    prior_cover_proof_type: Optional[str] = None
    prior_cover_schemes_json: Optional[List[Any]] = None
    # Late-joiner
    is_late_joiner: bool = False
    late_joiner_uncovered_years: Optional[int] = None
    # Conditions
    conditions_declared: bool = False
    declared_conditions_json: Optional[List[DeclaredCondition]] = None


class EnrollmentQuestionnaireResponse(BaseModel):
    id: int
    member_id: int
    scheme_id: int
    join_reason: str
    has_prior_cover: bool
    prior_cover_years: Optional[float] = None
    prior_cover_break_days: Optional[int] = None
    prior_cover_proof_type: Optional[str] = None
    prior_cover_schemes_json: Optional[List[Any]] = None
    is_late_joiner: bool
    late_joiner_uncovered_years: Optional[int] = None
    conditions_declared: bool
    declared_conditions_json: Optional[List[Any]] = None
    completed_by: int
    completed_at: Optional[datetime] = None
    status: str
    underwriting_decision_id: Optional[int] = None
    engine_outcome: Optional[str] = None

    model_config = {"from_attributes": True}
