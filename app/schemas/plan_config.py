from pydantic import BaseModel
from typing import Optional, List
from datetime import date


# ─── Plan Options ─────────────────────────────────────────────────────────────

class PlanOptionCreate(BaseModel):
    name: str
    code: str
    monthly_premium: int  # cents
    hospital_network: Optional[str] = "OPEN"
    day_to_day_type: Optional[str] = "NONE"
    care_coordination_required: bool = False
    gp_referral_required: bool = False
    benefit_year: Optional[int] = None
    tariff_multiplier: int = 100
    is_active: bool = True


class PlanOptionUpdate(BaseModel):
    name: Optional[str] = None
    monthly_premium: Optional[int] = None
    hospital_network: Optional[str] = None
    day_to_day_type: Optional[str] = None
    care_coordination_required: Optional[bool] = None
    gp_referral_required: Optional[bool] = None
    benefit_year: Optional[int] = None
    tariff_multiplier: Optional[int] = None
    is_active: Optional[bool] = None


class PlanOptionResponse(BaseModel):
    id: int
    scheme_id: int
    name: str
    code: str
    monthly_premium: int
    hospital_network: Optional[str] = None
    day_to_day_type: Optional[str] = None
    care_coordination_required: bool
    gp_referral_required: bool
    benefit_year: Optional[int] = None
    tariff_multiplier: int
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Benefit Limits ───────────────────────────────────────────────────────────

class BenefitLimitCreate(BaseModel):
    plan_option_id: int
    benefit_category: str
    limit_type: str  # RAND | VISITS | UNLIMITED
    limit_value: int  # cents or visit count
    applied_value: int = 0
    benefit_year: int


class BenefitLimitUpdate(BaseModel):
    limit_type: Optional[str] = None
    limit_value: Optional[int] = None
    applied_value: Optional[int] = None
    benefit_year: Optional[int] = None


class BenefitLimitResponse(BaseModel):
    id: int
    plan_option_id: int
    benefit_category: str
    limit_type: str
    limit_value: int
    applied_value: int
    benefit_year: int

    model_config = {"from_attributes": True}


class PaginatedBenefitLimitResponse(BaseModel):
    items: List[BenefitLimitResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Contribution Rates ───────────────────────────────────────────────────────

class ContributionRateCreate(BaseModel):
    plan_option_id: int
    member_type: str  # PRINCIPAL | ADULT_DEPENDANT | CHILD
    monthly_rate_cents: int
    effective_year: int


class ContributionRateUpdate(BaseModel):
    monthly_rate_cents: Optional[int] = None
    effective_year: Optional[int] = None


class ContributionRateResponse(BaseModel):
    id: int
    plan_option_id: int
    member_type: str
    monthly_rate_cents: int
    effective_year: int

    model_config = {"from_attributes": True}


# ─── Copayment Rules ──────────────────────────────────────────────────────────

class CopaymentRuleCreate(BaseModel):
    plan_option_id: Optional[int] = None
    trigger: str
    copayment_type: str  # PERCENTAGE | RAND_AMOUNT
    copayment_value: int
    description: Optional[str] = None
    is_upfront: bool = True
    is_active: bool = True


class CopaymentRuleUpdate(BaseModel):
    trigger: Optional[str] = None
    copayment_type: Optional[str] = None
    copayment_value: Optional[int] = None
    description: Optional[str] = None
    is_upfront: Optional[bool] = None
    is_active: Optional[bool] = None


class CopaymentRuleResponse(BaseModel):
    id: int
    scheme_id: int
    plan_option_id: Optional[int] = None
    trigger: str
    copayment_type: str
    copayment_value: int
    description: Optional[str] = None
    is_upfront: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Formulary Entries ────────────────────────────────────────────────────────

class FormularyCreate(BaseModel):
    plan_option_id: int
    formulary_type: str  # CHRONIC | ACUTE | ONCOLOGY | RADIOLOGY | PATHOLOGY
    nappi_code_id: Optional[int] = None
    tariff_code_id: Optional[int] = None
    cdl_condition: Optional[str] = None
    is_covered: bool = True
    is_preferred: bool = True
    reference_price_cents: Optional[int] = None
    max_quantity_per_script: Optional[int] = None
    max_scripts_per_period: Optional[int] = None
    period_days: Optional[int] = None
    copayment_if_non_formulary_pct: Optional[int] = 20
    effective_year: int


class FormularyUpdate(BaseModel):
    formulary_type: Optional[str] = None
    cdl_condition: Optional[str] = None
    is_covered: Optional[bool] = None
    is_preferred: Optional[bool] = None
    reference_price_cents: Optional[int] = None
    max_quantity_per_script: Optional[int] = None
    max_scripts_per_period: Optional[int] = None
    period_days: Optional[int] = None
    copayment_if_non_formulary_pct: Optional[int] = None
    effective_year: Optional[int] = None


class FormularyResponse(BaseModel):
    id: int
    plan_option_id: int
    formulary_type: str
    nappi_code_id: Optional[int] = None
    tariff_code_id: Optional[int] = None
    cdl_condition: Optional[str] = None
    is_covered: bool
    is_preferred: bool
    reference_price_cents: Optional[int] = None
    max_quantity_per_script: Optional[int] = None
    max_scripts_per_period: Optional[int] = None
    period_days: Optional[int] = None
    copayment_if_non_formulary_pct: Optional[int] = None
    effective_year: int

    model_config = {"from_attributes": True}


class PaginatedFormularyResponse(BaseModel):
    items: List[FormularyResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Provider Networks ────────────────────────────────────────────────────────

class ProviderNetworkCreate(BaseModel):
    provider_id: int
    network_type: str
    effective_from: date
    effective_to: Optional[date] = None


class ProviderNetworkUpdate(BaseModel):
    network_type: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class ProviderNetworkResponse(BaseModel):
    id: int
    provider_id: int
    scheme_id: int
    network_type: str
    effective_from: date
    effective_to: Optional[date] = None

    model_config = {"from_attributes": True}


class PaginatedProviderNetworkResponse(BaseModel):
    items: List[ProviderNetworkResponse]
    total: int
    page: int
    page_size: int
    pages: int
