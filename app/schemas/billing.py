from pydantic import BaseModel
from typing import Optional, List


class ContributionCalculatorRequest(BaseModel):
    plan_option_id: int
    adult_dependants: int = 0
    children: int = 0
    benefit_year: int


class ContributionLineResponse(BaseModel):
    member_type: str
    count: int
    rate_cents: int
    subtotal_cents: int


class ContributionCalculatorResponse(BaseModel):
    lines: List[ContributionLineResponse]
    total_monthly_cents: int
    child_cap_applied: bool
    children_billed: int
    children_free: int
    error: Optional[str] = None


class FormularyEntryResponse(BaseModel):
    id: int
    plan_option_id: int
    formulary_type: str
    cdl_condition: Optional[str] = None
    nappi_code: Optional[str] = None
    product_name: Optional[str] = None
    generic_name: Optional[str] = None
    is_covered: bool
    is_preferred: bool
    reference_price_cents: Optional[int] = None
    max_quantity_per_script: Optional[int] = None
    copayment_if_non_formulary_pct: Optional[int] = None
    effective_year: int

    model_config = {"from_attributes": True}


class PaginatedFormularyResponse(BaseModel):
    items: List[FormularyEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int


# --- Contribution Ledger ---

class BillingRunRequest(BaseModel):
    billing_month: str  # "YYYY-MM"


class BillingRunResponse(BaseModel):
    generated: int
    skipped: int
    total_active: int


class MemberContributionResponse(BaseModel):
    id: int
    member_id: int
    scheme_id: int
    billing_month: str
    principal_cents: int
    adult_dependant_count: int
    adult_dependant_cents: int
    child_count: int
    child_cents: int
    child_cap_applied: bool
    late_joiner_penalty_pct: int
    late_joiner_surcharge_cents: int
    amount_due_cents: int
    amount_paid_cents: int
    payment_date: Optional[str] = None
    payment_reference: Optional[str] = None
    status: str
    generated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentRecordRequest(BaseModel):
    amount_paid_cents: int
    payment_date: str  # "YYYY-MM-DD"
    payment_reference: Optional[str] = None


class MemberContributionScheduleResponse(BaseModel):
    months: List[MemberContributionResponse]
    next_collection: Optional[MemberContributionResponse] = None
