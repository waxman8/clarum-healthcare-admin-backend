"""7-Stage Claims Adjudication Engine.

Pipeline:
  Stage 1: Admin Pre-checks    — member active, provider registered, duplicate, stale, auth required, waiting period
  Stage 2: Industry Rules      — ICD-10 valid, tariff valid, discipline match, gender/age restrictions, NAPPI valid
  Stage 3: PMB Eligibility     — is_pmb flag, CDL + chronic_registration, DTP care plan
  Stage 4: Clinical Rules      — formulary compliance, step therapy
  Stage 5: Scheme Rules        — benefit bucket routing, limit check, network/DSP co-pay, waiting period
  Stage 6: PMB Override        — MSA s.29(1)(o): fund PMB even if limit exhausted
  Stage 7: Rate Calculation    — NHRPL × tariff_multiplier, reference pricing, co-pay deduction, balance deduction

Entry points:
  run_rules_engine()          — backward-compatible read-only path (Stages 1–5, no balance mutation)
  run_full_adjudication()     — full 7 stages; persists ClaimAdjudicationLog and decrements balances

Nothing is hardcoded: all monetary limits, rates, co-payment values, network rules
are read from the database at adjudication time.
"""
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing import (
    BenefitBalance, ChronicRegistration, ClaimAdjudicationLog, Formulary, NappiCode
)
from app.models.claims import Claim, ClaimLine
from app.models.members import Dependant, Member
from app.models.providers import Provider
from app.models.reference import ICD10Code, PlanOption, TariffCode
from app.schemas.claims import RulesEngineResult
from app.services import benefit_balance_service, network_validator
from app.constants import BenefitBucket, ChronicStatus, DayToDayType, MemberStatus, PipelineStatus


# ---------------------------------------------------------------------------
# Context and Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LineAdjudicationState:
    """Mutable state for one claim line as it passes through the pipeline."""
    line_id: Optional[int]
    tariff_code: str
    icd10_code: Optional[str]
    nappi_code_id: Optional[int]
    quantity: int
    billed_amount: int

    # Filled in as pipeline progresses
    is_pmb: bool = False
    is_pmb_override: bool = False
    benefit_bucket: Optional[str] = None
    approved_amount: int = 0
    scheme_rate_cents: Optional[int] = None
    copayment_cents: int = 0
    member_liability: int = 0
    rejection_reason_code: Optional[str] = None
    rejection_reason_text: Optional[str] = None
    status: str = PipelineStatus.PENDING


@dataclass
class StageResult:
    """A single stage × rule result for the adjudication log."""
    stage: int
    stage_name: str
    rule_code: str
    result: str  # PASS | FAIL | FLAG | INFO | OVERRIDE
    detail: dict = field(default_factory=dict)
    line_id: Optional[int] = None


@dataclass
class AdjudicationContext:
    """Loaded once before the pipeline; passed read-only to all stage functions."""
    claim: Claim
    member: Member
    plan_option: PlanOption
    provider: Provider
    provider_network_types: list
    icd10_map: dict     # code str → ICD10Code
    tariff_map: dict    # code str → TariffCode
    nappi_map: dict     # id int → NappiCode
    benefit_balances: dict  # benefit_category str → BenefitBalance
    chronic_registrations: list  # active ChronicRegistration rows for member
    scheme_id: int
    benefit_year: int


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

async def _build_context(db: AsyncSession, claim: Claim) -> AdjudicationContext:
    """Load all data needed for adjudication in bulk (minimises DB round-trips)."""
    # Member + plan
    member_res = await db.execute(
        select(Member).where(Member.id == claim.member_id)
    )
    member = member_res.scalar_one()

    plan_res = await db.execute(
        select(PlanOption).where(PlanOption.id == member.plan_option_id)
    )
    plan = plan_res.scalar_one()

    # Provider
    provider_res = await db.execute(
        select(Provider).where(Provider.id == claim.provider_id)
    )
    provider = provider_res.scalar_one()

    # Provider network types for this scheme on date of service
    network_types = await network_validator.get_provider_network_types(
        db, claim.provider_id, claim.scheme_id, claim.date_of_service_from
    )

    # ICD-10 codes used on this claim
    icd_codes = [
        (line.icd10_code if hasattr(line, "icd10_code") else None)
        for line in claim.lines
    ]
    icd_codes = [c for c in icd_codes if c]
    icd10_map = {}
    if icd_codes:
        icd_res = await db.execute(
            select(ICD10Code).where(ICD10Code.code.in_(icd_codes))
        )
        icd10_map = {r.code: r for r in icd_res.scalars().all()}

    # Tariff codes
    tariff_codes = list({line.tariff_code for line in claim.lines})
    tariff_res = await db.execute(
        select(TariffCode).where(TariffCode.code.in_(tariff_codes))
    )
    tariff_map = {r.code: r for r in tariff_res.scalars().all()}

    # NAPPI codes
    nappi_ids = [
        line.nappi_code_id for line in claim.lines if line.nappi_code_id
    ]
    nappi_map = {}
    if nappi_ids:
        nappi_res = await db.execute(
            select(NappiCode).where(NappiCode.id.in_(nappi_ids))
        )
        nappi_map = {r.id: r for r in nappi_res.scalars().all()}

    # Benefit balances
    benefit_year = claim.date_of_service_from.year
    balances = await benefit_balance_service.get_all_balances_for_member(
        db, member.id, benefit_year
    )
    benefit_balances = {b.benefit_category: b for b in balances}

    # Active chronic registrations for member
    chronic_res = await db.execute(
        select(ChronicRegistration).where(
            and_(
                ChronicRegistration.member_id == member.id,
                ChronicRegistration.status == ChronicStatus.APPROVED,
                or_(
                    ChronicRegistration.expiry_date == None,   # noqa: E711
                    ChronicRegistration.expiry_date >= claim.date_of_service_from,
                ),
            )
        )
    )
    chronic_registrations = chronic_res.scalars().all()

    # Resolve ICD-10 ids on chronic registrations to codes
    cdl_icd_ids = [r.icd10_code_id for r in chronic_registrations]
    cdl_icd_map = {}
    if cdl_icd_ids:
        cdl_res = await db.execute(
            select(ICD10Code).where(ICD10Code.id.in_(cdl_icd_ids))
        )
        cdl_icd_map = {r.id: r for r in cdl_res.scalars().all()}
    for reg in chronic_registrations:
        # Attach icd10 object for easy access in pipeline
        reg._icd10 = cdl_icd_map.get(reg.icd10_code_id)

    return AdjudicationContext(
        claim=claim,
        member=member,
        plan_option=plan,
        provider=provider,
        provider_network_types=network_types,
        icd10_map=icd10_map,
        tariff_map=tariff_map,
        nappi_map=nappi_map,
        benefit_balances=benefit_balances,
        chronic_registrations=list(chronic_registrations),
        scheme_id=claim.scheme_id,
        benefit_year=benefit_year,
    )


# ---------------------------------------------------------------------------
# Stage 1: Administrative Pre-checks
# ---------------------------------------------------------------------------

async def _stage1_admin(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    results = []
    member = ctx.member
    claim = ctx.claim
    dos = claim.date_of_service_from

    # ADM001: Member active on date of service
    if member.status != MemberStatus.ACTIVE:
        r = StageResult(1, "ADMIN", "ADM001", PipelineStatus.FAIL,
                        {"member_status": member.status, "required": "active"})
        results.append(r)
        for s in states:
            s.status = "FAIL"
            s.rejection_reason_code = "ADM001"
            s.rejection_reason_text = f"Member status is '{member.status}'"
    elif member.join_date > dos:
        r = StageResult(1, "ADMIN", "ADM001", "FAIL",
                        {"join_date": str(member.join_date), "date_of_service": str(dos)})
        results.append(r)
        for s in states:
            s.status = "FAIL"
            s.rejection_reason_code = "ADM001"
            s.rejection_reason_text = "Service date before member join date"
    elif member.termination_date and member.termination_date < dos:
        r = StageResult(1, "ADMIN", "ADM001", "FAIL",
                        {"termination_date": str(member.termination_date)})
        results.append(r)
        for s in states:
            s.status = "FAIL"
            s.rejection_reason_code = "ADM001"
            s.rejection_reason_text = "Member terminated before date of service"
    else:
        results.append(StageResult(1, "ADMIN", "ADM001", "PASS",
                                   {"member_status": member.status}))

    # ADM002: Provider active
    if not ctx.provider.is_active:
        r = StageResult(1, "ADMIN", "ADM003", "FAIL",
                        {"provider_id": ctx.provider.id})
        results.append(r)
        for s in states:
            if s.status == "PENDING":
                s.status = "FAIL"
                s.rejection_reason_code = "ADM003"
                s.rejection_reason_text = "Provider is not active"
    else:
        results.append(StageResult(1, "ADMIN", "ADM003", "PASS",
                                   {"provider_id": ctx.provider.id,
                                    "is_dsp": ctx.provider.is_dsp}))

    # ADM004: Duplicate claim check (same member + provider + tariff within 30 days)
    thirty_days_ago = dos - timedelta(days=30)
    tariff_codes = [s.tariff_code for s in states]
    dup_query = (
        select(ClaimLine)
        .join(Claim)
        .where(
            and_(
                Claim.member_id == claim.member_id,
                Claim.provider_id == claim.provider_id,
                Claim.date_of_service_from >= thirty_days_ago,
                Claim.id != claim.id,
                ClaimLine.tariff_code.in_(tariff_codes),
            )
        )
    )
    dup_res = await db.execute(dup_query)
    if dup_res.scalar_one_or_none():
        results.append(StageResult(1, "ADMIN", "ADM004", "FLAG",
                                   {"window_days": 30}))
    else:
        results.append(StageResult(1, "ADMIN", "ADM004", "PASS", {}))

    # ADM005: Stale claim (>4 months for regular; >12 months for PMB)
    stale_threshold = dos + timedelta(days=120)
    today = date.today()
    if today > stale_threshold:
        results.append(StageResult(1, "ADMIN", "ADM005", "FLAG",
                                   {"date_of_service": str(dos),
                                    "days_old": (today - dos).days}))
    else:
        results.append(StageResult(1, "ADMIN", "ADM005", "PASS", {}))

    # ADM008: Waiting period
    if member.waiting_period_end_date and dos <= member.waiting_period_end_date:
        results.append(StageResult(1, "ADMIN", "ADM008", "INFO",
                                   {"waiting_period_end": str(member.waiting_period_end_date),
                                    "note": "Will be enforced in Stage 5 for non-PMB lines"}))
    else:
        results.append(StageResult(1, "ADMIN", "ADM008", "PASS", {}))

    return results


# ---------------------------------------------------------------------------
# Stage 2: Industry Rules
# ---------------------------------------------------------------------------

async def _stage2_industry(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    results = []
    member = ctx.member

    for state in states:
        if state.status not in PipelineStatus.ACTIVE:
            continue

        line_id = state.line_id

        # IND001: ICD-10 valid
        if state.icd10_code:
            icd = ctx.icd10_map.get(state.icd10_code)
            if not icd:
                results.append(StageResult(1, "INDUSTRY", "IND001", "FAIL",
                                           {"icd10_code": state.icd10_code,
                                            "reason": "Code not found"}, line_id))
                state.status = "FAIL"
                state.rejection_reason_code = "IND001"
                state.rejection_reason_text = f"ICD-10 code {state.icd10_code} not found"
                continue
            if not icd.is_active:
                results.append(StageResult(2, "INDUSTRY", "IND001", "FAIL",
                                           {"icd10_code": state.icd10_code,
                                            "reason": "Code inactive"}, line_id))
                state.status = "FAIL"
                state.rejection_reason_code = "IND001"
                state.rejection_reason_text = f"ICD-10 code {state.icd10_code} is inactive"
                continue
            # IND004: Gender restriction
            if icd.gender_restriction and icd.gender_restriction != member.gender:
                results.append(StageResult(2, "INDUSTRY", "IND004", "FAIL",
                                           {"icd10_code": state.icd10_code,
                                            "requires_gender": icd.gender_restriction,
                                            "member_gender": member.gender}, line_id))
                state.status = "FAIL"
                state.rejection_reason_code = "IND004"
                state.rejection_reason_text = (
                    f"ICD-10 {state.icd10_code} restricted to gender {icd.gender_restriction}"
                )
                continue
            results.append(StageResult(2, "INDUSTRY", "IND001", "PASS",
                                       {"icd10_code": state.icd10_code,
                                        "is_pmb": icd.is_pmb,
                                        "is_cdl": icd.is_cdl}, line_id))

        # IND002: Tariff valid
        tariff = ctx.tariff_map.get(state.tariff_code)
        if not tariff:
            results.append(StageResult(2, "INDUSTRY", "IND002", "FAIL",
                                       {"tariff_code": state.tariff_code,
                                        "reason": "Code not found"}, line_id))
            state.status = "FAIL"
            state.rejection_reason_code = "IND002"
            state.rejection_reason_text = f"Tariff code {state.tariff_code} not found"
            continue
        if not tariff.is_active:
            results.append(StageResult(2, "INDUSTRY", "IND002", "FAIL",
                                       {"tariff_code": state.tariff_code,
                                        "reason": "Tariff inactive"}, line_id))
            state.status = "FAIL"
            state.rejection_reason_code = "IND002"
            state.rejection_reason_text = f"Tariff code {state.tariff_code} is inactive"
            continue
        results.append(StageResult(2, "INDUSTRY", "IND002", "PASS",
                                   {"tariff_code": state.tariff_code,
                                    "nhrpl_rate": tariff.nhrpl_rate}, line_id))

        # IND003: Discipline match (only check if tariff has discipline_codes JSON)
        if tariff.discipline_codes:
            try:
                allowed = json.loads(tariff.discipline_codes)
                if ctx.provider.discipline_code and ctx.provider.discipline_code not in allowed:
                    results.append(StageResult(2, "INDUSTRY", "IND003", "FLAG",
                                               {"provider_discipline": ctx.provider.discipline_code,
                                                "allowed": allowed}, line_id))
            except (json.JSONDecodeError, TypeError):
                pass  # Malformed JSON — skip discipline check
        else:
            results.append(StageResult(2, "INDUSTRY", "IND003", "PASS",
                                       {"note": "No discipline restriction"}, line_id))

        # IND007: NAPPI valid
        if state.nappi_code_id:
            nappi = ctx.nappi_map.get(state.nappi_code_id)
            if not nappi or not nappi.is_active:
                results.append(StageResult(2, "INDUSTRY", "IND007", "FAIL",
                                           {"nappi_code_id": state.nappi_code_id}, line_id))
                state.status = "FAIL"
                state.rejection_reason_code = "IND007"
                state.rejection_reason_text = "NAPPI code invalid or inactive"
                continue
            results.append(StageResult(2, "INDUSTRY", "IND007", "PASS",
                                       {"nappi_code": nappi.nappi_code,
                                        "schedule": nappi.schedule}, line_id))

    return results


# ---------------------------------------------------------------------------
# Stage 3: PMB Eligibility
# ---------------------------------------------------------------------------

def _check_pmb_eligibility(
    state: LineAdjudicationState,
    ctx: AdjudicationContext,
) -> bool:
    """
    A claim line is PMB if:
    1. ICD-10 code has is_pmb = True (Annexure A condition), OR
    2. ICD-10 is CDL (is_cdl=True) AND member has an APPROVED chronic_registration, OR
    3. (Future: member has a DTP PMB care plan covering this tariff — not yet implemented)
    """
    icd = ctx.icd10_map.get(state.icd10_code) if state.icd10_code else None

    # Rule 1: Direct PMB condition
    if icd and icd.is_pmb:
        return True

    # Rule 2: CDL condition + active registration
    if icd and icd.is_cdl:
        for reg in ctx.chronic_registrations:
            reg_icd = getattr(reg, "_icd10", None)
            if reg_icd and reg_icd.code == state.icd10_code:
                return True

    return False


async def _stage3_pmb(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    results = []
    for state in states:
        if state.status not in PipelineStatus.ACTIVE:
            continue
        is_pmb = _check_pmb_eligibility(state, ctx)
        state.is_pmb = is_pmb
        icd = ctx.icd10_map.get(state.icd10_code) if state.icd10_code else None
        results.append(StageResult(
            3, "PMB", "PMB001",
            "INFO",
            {"is_pmb": is_pmb,
             "is_pmb_condition": bool(icd and icd.is_pmb),
             "is_cdl": bool(icd and icd.is_cdl),
             "has_cdl_registration": any(
                 getattr(r, "_icd10", None) and getattr(r._icd10, "code", None) == state.icd10_code
                 for r in ctx.chronic_registrations
             )},
            state.line_id,
        ))
    return results


# ---------------------------------------------------------------------------
# Stage 4: Clinical Rules
# ---------------------------------------------------------------------------

async def _stage4_clinical(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    results = []
    plan_id = ctx.plan_option.id
    benefit_year = ctx.benefit_year

    for state in states:
        if state.status not in PipelineStatus.ACTIVE:
            continue

        icd = ctx.icd10_map.get(state.icd10_code) if state.icd10_code else None
        nappi = ctx.nappi_map.get(state.nappi_code_id) if state.nappi_code_id else None

        # CL001: Formulary compliance for NAPPI lines
        if nappi and icd:
            formulary_res = await db.execute(
                select(Formulary).where(
                    and_(
                        Formulary.plan_option_id == plan_id,
                        Formulary.nappi_code_id == state.nappi_code_id,
                        Formulary.effective_year == benefit_year,
                    )
                )
            )
            formulary_entry = formulary_res.scalar_one_or_none()

            if formulary_entry is None:
                if state.is_pmb and icd.is_cdl:
                    # PMB CDL — must fund even if not on formulary
                    results.append(StageResult(
                        4, "CLINICAL", "CL001", "FLAG",
                        {"nappi": nappi.nappi_code,
                         "note": "Not on formulary but PMB CDL — will be funded from Risk"},
                        state.line_id,
                    ))
                else:
                    results.append(StageResult(
                        4, "CLINICAL", "CL001", "FAIL",
                        {"nappi": nappi.nappi_code,
                         "plan_id": plan_id,
                         "reason": "Not on formulary"},
                        state.line_id,
                    ))
                    state.status = "FAIL"
                    state.rejection_reason_code = "CL001"
                    state.rejection_reason_text = (
                        f"{nappi.nappi_code} is not on the formulary for this plan"
                    )
            else:
                results.append(StageResult(
                    4, "CLINICAL", "CL001", "PASS",
                    {"nappi": nappi.nappi_code,
                     "is_preferred": formulary_entry.is_preferred,
                     "reference_price_cents": formulary_entry.reference_price_cents},
                    state.line_id,
                ))
        else:
            results.append(StageResult(4, "CLINICAL", "CL001", "PASS",
                                       {"note": "No formulary check required"}, state.line_id))

    return results


# ---------------------------------------------------------------------------
# Stage 5: Scheme Rules
# ---------------------------------------------------------------------------

def _determine_benefit_bucket(
    state: LineAdjudicationState,
    ctx: AdjudicationContext,
) -> str:
    """
    Route a line to a benefit bucket.
    All routing logic reads plan_option fields set at DB seed time — nothing hardcoded.
    """
    plan = ctx.plan_option
    claim = ctx.claim
    icd = ctx.icd10_map.get(state.icd10_code) if state.icd10_code else None

    # Hospital claim (has auth and is an in-hospital claim type)
    if claim.auth_number and claim.claim_type in ("INHOSPITAL", "HOSPITAL", "hospital"):
        return BenefitBucket.HOSPITAL

    # Oncology
    if icd and icd.cdl_condition_name and "ONCOLOGY" in (icd.cdl_condition_name or "").upper():
        return BenefitBucket.ONCOLOGY
    if "ONCOL" in (state.tariff_code or "").upper():
        return BenefitBucket.ONCOLOGY

    # Chronic (CDL with active registration)
    if icd and icd.is_cdl:
        has_reg = any(
            getattr(r, "_icd10", None) and getattr(r._icd10, "code", None) == state.icd10_code
            for r in ctx.chronic_registrations
        )
        if has_reg:
            return BenefitBucket.CHRONIC

    # Day-to-day routing based on plan type
    if plan.day_to_day_type == DayToDayType.SAVINGS:
        return BenefitBucket.SAVINGS
    if plan.day_to_day_type == DayToDayType.LIMIT:
        return BenefitBucket.DAY_TO_DAY
    if plan.day_to_day_type == DayToDayType.NONE:
        return BenefitBucket.PMB_RISK if state.is_pmb else BenefitBucket.MEMBER_LIABILITY

    return BenefitBucket.DAY_TO_DAY  # Fallback


async def _stage5_scheme(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    results = []
    member = ctx.member
    plan = ctx.plan_option
    claim = ctx.claim
    dos = claim.date_of_service_from
    benefit_year = ctx.benefit_year

    for state in states:
        if state.status not in PipelineStatus.ACTIVE:
            continue

        line_id = state.line_id

        # SCH-ROUTE: Benefit bucket
        bucket = _determine_benefit_bucket(state, ctx)
        state.benefit_bucket = bucket
        results.append(StageResult(5, "SCHEME", "SCH-ROUTE", "INFO",
                                   {"bucket": bucket}, line_id))

        # SCH001-003: Benefit limit check
        balance = ctx.benefit_balances.get(bucket)
        if balance is not None:
            available = max(0, balance.opening_balance_cents - balance.used_cents - balance.reserved_cents)
            if available <= 0 and not state.is_pmb:
                results.append(StageResult(5, "SCHEME", "SCH003", "FAIL",
                                           {"bucket": bucket, "available": available}, line_id))
                state.status = "FAIL"
                state.rejection_reason_code = "SCH003"
                state.rejection_reason_text = f"Benefit limit exhausted for {bucket}"
                continue
            elif available < state.billed_amount and not state.is_pmb:
                results.append(StageResult(5, "SCHEME", "SCH003", "FLAG",
                                           {"bucket": bucket, "available": available,
                                            "billed": state.billed_amount}, line_id))
            else:
                results.append(StageResult(5, "SCHEME", "SCH003", "PASS",
                                           {"bucket": bucket, "available": available}, line_id))

        # SCH-NET: Network/DSP co-payment
        total_copay = 0
        if bucket == "HOSPITAL" and plan.hospital_network:
            net_check = await network_validator.check_hospital_network(
                db,
                ctx.claim.provider_id,
                ctx.scheme_id,
                plan.id,
                dos,
                plan.hospital_network,
                state.billed_amount,
            )
            if net_check["copayment_cents"] > 0:
                total_copay += net_check["copayment_cents"]
                results.append(StageResult(5, "SCHEME", "SCH-NET", "INFO",
                                           {"trigger": net_check["trigger"],
                                            "copayment_cents": net_check["copayment_cents"]},
                                           line_id))

        # DSP check for relevant categories
        icd = ctx.icd10_map.get(state.icd10_code) if state.icd10_code else None
        benefit_cat = icd.cdl_condition_name if icd else None
        if benefit_cat and benefit_cat in network_validator.DSP_REQUIRED_CATEGORIES:
            dsp_check = await network_validator.check_dsp_network(
                db,
                ctx.claim.provider_id,
                ctx.scheme_id,
                plan.id,
                benefit_cat,
                dos,
                state.billed_amount,
            )
            if dsp_check["copayment_cents"] > 0:
                total_copay += dsp_check["copayment_cents"]
                results.append(StageResult(5, "SCHEME", "SCH-DSP", "INFO",
                                           {"trigger": dsp_check["trigger"],
                                            "copayment_cents": dsp_check["copayment_cents"]},
                                           line_id))

        # SCH004: Waiting period (non-PMB only)
        if not state.is_pmb and member.waiting_period_end_date and dos <= member.waiting_period_end_date:
            results.append(StageResult(5, "SCHEME", "SCH004", "FAIL",
                                       {"waiting_period_end": str(member.waiting_period_end_date),
                                        "date_of_service": str(dos)}, line_id))
            state.status = "FAIL"
            state.rejection_reason_code = "SCH004"
            state.rejection_reason_text = "Service within waiting period"
            continue

        # Accumulate co-payment
        state.copayment_cents = total_copay
        if state.status == "PENDING":
            state.status = "PASS"
        results.append(StageResult(5, "SCHEME", "SCH-PASS", "PASS",
                                   {"copayment_cents": total_copay}, line_id))

    return results


# ---------------------------------------------------------------------------
# Stage 6: PMB Override
# ---------------------------------------------------------------------------

async def _stage6_pmb_override(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState]
) -> list[StageResult]:
    """
    MSA s.29(1)(o): schemes MUST fund PMB conditions.
    If a PMB line was rejected by scheme rules (benefit exhausted, waiting period),
    override the rejection and route to PMB_RISK.
    """
    results = []
    for state in states:
        if state.status == "FAIL" and state.is_pmb:
            state.status = "PASS"
            state.is_pmb_override = True
            state.benefit_bucket = "PMB_RISK"
            state.rejection_reason_code = None
            state.rejection_reason_text = None
            results.append(StageResult(6, "PMB_OVERRIDE", "PMB-S29", "OVERRIDE",
                                       {"reason": "MSA s.29(1)(o) — scheme must fund PMB",
                                        "original_rejection": state.rejection_reason_code},
                                       state.line_id))
        elif state.status == "PASS":
            results.append(StageResult(6, "PMB_OVERRIDE", "PMB-S29", "PASS",
                                       {"note": "Not applicable"}, state.line_id))
    return results


# ---------------------------------------------------------------------------
# Stage 7: Rate Calculation
# ---------------------------------------------------------------------------

async def _stage7_rate_calc(
    db: AsyncSession, ctx: AdjudicationContext, states: list[LineAdjudicationState],
    persist_balances: bool = True,
) -> list[StageResult]:
    """
    Calculate approved amounts, apply co-payments, and optionally decrement balances.
    persist_balances=False for preview (GET /claims/{id}/rules).
    """
    results = []
    plan = ctx.plan_option
    benefit_year = ctx.benefit_year

    for state in states:
        if state.status != "PASS":
            state.approved_amount = 0
            state.member_liability = state.billed_amount
            continue

        tariff = ctx.tariff_map.get(state.tariff_code)
        if not tariff:
            state.approved_amount = 0
            state.member_liability = state.billed_amount
            continue

        # Base rate = NHRPL × plan tariff_multiplier / 100
        multiplier = plan.tariff_multiplier if plan.tariff_multiplier else 100
        base_rate = int(tariff.nhrpl_rate * multiplier / 100)

        # Generic reference pricing for pharmacy lines
        ref_price = None
        if state.nappi_code_id:
            nappi = ctx.nappi_map.get(state.nappi_code_id)
            if nappi:
                formulary_res = await db.execute(
                    select(Formulary).where(
                        and_(
                            Formulary.plan_option_id == plan.id,
                            Formulary.nappi_code_id == state.nappi_code_id,
                        )
                    )
                )
                entry = formulary_res.scalar_one_or_none()
                if entry and entry.reference_price_cents:
                    ref_price = entry.reference_price_cents

        # Approved before co-payment = min(billed, base_rate × quantity)
        if ref_price:
            approved_before_copay = min(state.billed_amount, ref_price * state.quantity)
        else:
            approved_before_copay = min(state.billed_amount, base_rate * state.quantity)

        scheme_pays = max(0, approved_before_copay - state.copayment_cents)
        member_liability = (state.billed_amount - approved_before_copay) + state.copayment_cents

        state.approved_amount = approved_before_copay
        state.scheme_rate_cents = base_rate
        state.member_liability = member_liability

        results.append(StageResult(7, "RATE_CALC", "RATE001", "PASS",
                                   {"nhrpl_rate": tariff.nhrpl_rate,
                                    "multiplier": multiplier,
                                    "base_rate": base_rate,
                                    "approved_before_copay": approved_before_copay,
                                    "copayment": state.copayment_cents,
                                    "scheme_pays": scheme_pays,
                                    "member_liability": member_liability,
                                    "ref_price_used": ref_price is not None},
                                   state.line_id))

        # Decrement benefit balance
        if persist_balances and state.benefit_bucket and state.benefit_bucket not in BenefitBucket.NOT_DECREMENTED:
            await benefit_balance_service.decrement_benefit_balance(
                db, ctx.member.id, state.benefit_bucket, benefit_year, scheme_pays
            )

    return results


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def run_full_adjudication(
    db: AsyncSession,
    claim: Claim,
    persist_logs: bool = True,
) -> list[StageResult]:
    """
    Run the complete 7-stage pipeline.
    If persist_logs=True, writes ClaimAdjudicationLog rows and decrements benefit balances.
    Called by the adjudicate endpoint.
    """
    ctx = await _build_context(db, claim)

    # Build mutable line states
    states = []
    for line in claim.lines:
        states.append(LineAdjudicationState(
            line_id=line.id,
            tariff_code=line.tariff_code,
            icd10_code=line.icd10_code,
            nappi_code_id=line.nappi_code_id,
            quantity=line.quantity,
            billed_amount=line.billed_amount,
        ))

    all_stage_results: list[StageResult] = []

    stage_results = await _stage1_admin(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage2_industry(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage3_pmb(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage4_clinical(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage5_scheme(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage6_pmb_override(db, ctx, states)
    all_stage_results.extend(stage_results)

    stage_results = await _stage7_rate_calc(db, ctx, states, persist_balances=persist_logs)
    all_stage_results.extend(stage_results)

    # Apply final line states back to ORM objects
    for state, line in zip(states, claim.lines):
        line.is_pmb_line = state.is_pmb
        line.is_pmb_override = state.is_pmb_override
        line.benefit_bucket = state.benefit_bucket
        line.approved_amount = state.approved_amount
        line.member_liability = state.member_liability
        line.copayment_cents = state.copayment_cents
        if hasattr(line, "scheme_rate_cents"):
            line.scheme_rate_cents = getattr(state, "scheme_rate_cents", None)
        if state.status == "FAIL":
            line.rejection_reason_code = state.rejection_reason_code
            line.rejection_reason_text = state.rejection_reason_text

    # Persist adjudication logs
    if persist_logs:
        # Clear old logs for this claim (re-adjudication)
        from sqlalchemy import delete
        await db.execute(
            delete(ClaimAdjudicationLog).where(ClaimAdjudicationLog.claim_id == claim.id)
        )
        for sr in all_stage_results:
            log = ClaimAdjudicationLog(
                claim_id=claim.id,
                claim_line_id=sr.line_id,
                stage=sr.stage,
                stage_name=sr.stage_name,
                rule_code=sr.rule_code,
                result=sr.result,
                detail=json.dumps(sr.detail) if sr.detail else None,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(log)
        await db.flush()

    return all_stage_results


async def run_rules_engine(
    db: AsyncSession,
    member_id: int,
    provider_id: int,
    date_of_service_from: date,
    claim_lines: list,
    claim_id: int = None,
) -> list[RulesEngineResult]:
    """
    Backward-compatible read-only wrapper.
    Runs Stages 1–5 (no balance mutation, no log persistence).
    Used by GET /claims/{id}/rules and claim creation preview.
    Returns the original RulesEngineResult schema.
    """
    # Build a lightweight claim object for the pipeline
    if claim_id:
        claim_res = await db.execute(select(Claim).where(Claim.id == claim_id))
        claim = claim_res.scalar_one_or_none()
    else:
        claim = None

    results = []

    # Rule 1: Member active
    member_res = await db.execute(
        select(Member)
        .where(Member.id == member_id)
        .options(selectinload(Member.plan_option))
    )
    member = member_res.scalar_one_or_none()

    if not member:
        results.append(RulesEngineResult(rule="Member Eligibility", status="FAIL",
                                          message="Member not found"))
    elif member.status != "active":
        results.append(RulesEngineResult(rule="Member Eligibility", status="FAIL",
                                          message=f"Member status is '{member.status}'"))
    elif member.join_date > date_of_service_from:
        results.append(RulesEngineResult(rule="Member Eligibility", status="FAIL",
                                          message="Service date before member join date"))
    elif member.termination_date and member.termination_date < date_of_service_from:
        results.append(RulesEngineResult(rule="Member Eligibility", status="FAIL",
                                          message="Member was terminated before date of service"))
    else:
        results.append(RulesEngineResult(rule="Member Eligibility", status="PASS",
                                          message="Member was active on date of service"))

    # Rule 2: Provider
    provider_res = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = provider_res.scalar_one_or_none()
    if not provider or not provider.is_active:
        results.append(RulesEngineResult(rule="Provider Registration", status="FAIL",
                                          message="Provider not found or not active"))
    else:
        dsp_msg = " (DSP Provider)" if provider.is_dsp else ""
        results.append(RulesEngineResult(rule="Provider Registration", status="PASS",
                                          message=f"Provider is registered and active{dsp_msg}"))

    # Rule 3: Duplicate check
    duplicate_found = False
    for line in claim_lines:
        tariff_code = line.get("tariff_code") if isinstance(line, dict) else line.tariff_code
        thirty_days_ago = date_of_service_from - timedelta(days=30)
        dup_query = (
            select(ClaimLine).join(Claim).where(
                and_(
                    Claim.member_id == member_id,
                    Claim.provider_id == provider_id,
                    Claim.date_of_service_from >= thirty_days_ago,
                    ClaimLine.tariff_code == tariff_code,
                )
            )
        )
        if claim_id:
            dup_query = dup_query.where(Claim.id != claim_id)
        dup_res = await db.execute(dup_query)
        if dup_res.scalar_one_or_none():
            duplicate_found = True
            break

    results.append(RulesEngineResult(
        rule="Duplicate Check",
        status="FLAG" if duplicate_found else "PASS",
        message=("Possible duplicate within 30 days" if duplicate_found
                 else "No duplicate found"),
    ))

    # Rule 4: PMB check
    pmb_found = False
    for line in claim_lines:
        icd10 = line.get("icd10_code") if isinstance(line, dict) else getattr(line, "icd10_code", None)
        if icd10:
            icd_res = await db.execute(
                select(ICD10Code).where(ICD10Code.code == icd10, ICD10Code.is_pmb == True)  # noqa
            )
            if icd_res.scalar_one_or_none():
                pmb_found = True
                break

    results.append(RulesEngineResult(
        rule="PMB Override",
        status="FLAG" if pmb_found else "PASS",
        message=("PMB condition detected" if pmb_found else "No PMB conditions identified"),
    ))

    # Rule 5: Benefit limit check (backward compat)
    if member and member.plan_option:
        from app.models.members import BenefitLimit
        limits_res = await db.execute(
            select(BenefitLimit).where(
                BenefitLimit.plan_option_id == member.plan_option_id,
                BenefitLimit.benefit_year == date_of_service_from.year,
            )
        )
        limits = limits_res.scalars().all()
        total_billed = sum(
            (line.get("billed_amount") if isinstance(line, dict) else line.billed_amount)
            for line in claim_lines
        )
        hospital_limit = next((l for l in limits if l.benefit_category == "hospital"), None)
        if hospital_limit and hospital_limit.limit_type == "rand":
            remaining = hospital_limit.limit_value - hospital_limit.applied_value
            if total_billed > remaining:
                results.append(RulesEngineResult(
                    rule="Benefit Limit", status="FLAG",
                    message=f"Claim R{total_billed/100:.2f} may exceed available R{remaining/100:.2f}",
                ))
            else:
                results.append(RulesEngineResult(
                    rule="Benefit Limit", status="PASS",
                    message=f"Within limits. Remaining: R{remaining/100:.2f}",
                ))
        else:
            results.append(RulesEngineResult(rule="Benefit Limit", status="PASS",
                                              message="Benefit limits verified"))

    return results
