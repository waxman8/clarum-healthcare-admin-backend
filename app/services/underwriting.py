"""Underwriting service — business logic for member enrollment decisions.

Underwriting is the member enrollment domain. It evaluates applications,
assigns waiting periods, calculates late-joiner penalties, and produces an
enrolled member with a complete underwriting profile. It has nothing to do
with claims adjudication.
"""
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.underwriting import UnderwritingDecision, MemberConditionExclusion, EnrollmentQuestionnaire
from app.models.members import Member
from app.schemas.underwriting import (
    UnderwritingDecisionCreate,
    MemberConditionExclusionCreate,
    UnderwritingPreviewRequest,
    UnderwritingPreviewResponse,
    EnrollmentQuestionnaireCreate,
    EnrollmentQuestionnaireResponse,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIVE_DECISIONS = ("approved", "conditionally_approved")

# MSA Regulation 8 late-joiner penalty bands
# Key = minimum uncovered years (inclusive), Value = penalty %
LATE_JOINER_BANDS = [
    (15, 75),
    (10, 50),
    (5, 25),
    (1, 5),
]

# Prior cover break threshold: gap > 90 days = loss of continuity
PRIOR_COVER_BREAK_THRESHOLD_DAYS = 90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_months(dt: date, months: int) -> date:
    """Add calendar months to a date, clamping to month-end on overflow."""
    month = dt.month + months
    year = dt.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))


def compute_wp_and_penalty(
    effective_date: date,
    has_prior_cover: bool,
    prior_cover_break_days: Optional[int],
    is_late_joiner: bool,
    late_joiner_uncovered_years: Optional[int],
    base_monthly_contribution: Optional[int] = None,
) -> UnderwritingPreviewResponse:
    """Compute waiting-period end date and late-joiner penalty band.

    Rules (MSA):
    - General WP is 3 months unless prior cover is proven with no break > 90 days.
    - PMB conditions are never subject to a waiting period (enforced at the
      exclusion level, not here).
    - Late-joiner penalty is a fixed band per Regulation 8, based on uncovered years.
    """
    # General waiting period
    has_continuity = (
        has_prior_cover
        and (prior_cover_break_days is None or prior_cover_break_days <= PRIOR_COVER_BREAK_THRESHOLD_DAYS)
    )
    if has_continuity:
        general_wp_months = 0
        general_wp_end_date = None
    else:
        general_wp_months = 3
        general_wp_end_date = _add_months(effective_date, 3)

    # Late-joiner penalty
    penalty_pct = 0
    if is_late_joiner and late_joiner_uncovered_years is not None:
        for min_years, pct in LATE_JOINER_BANDS:
            if late_joiner_uncovered_years >= min_years:
                penalty_pct = pct
                break

    # Total contribution after penalty
    total_monthly_contribution = None
    if base_monthly_contribution is not None:
        total_monthly_contribution = int(
            base_monthly_contribution * (1 + penalty_pct / 100)
        )

    return UnderwritingPreviewResponse(
        general_wp_months=general_wp_months,
        general_wp_end_date=general_wp_end_date,
        is_late_joiner=is_late_joiner,
        late_joiner_penalty_pct=penalty_pct,
        total_monthly_contribution=total_monthly_contribution,
    )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def create_decision(
    db: AsyncSession,
    data: UnderwritingDecisionCreate,
    scheme_id: int,
    created_by: int,
) -> UnderwritingDecision:
    """Create an underwriting decision for a member.

    Atomicity guarantee (via get_db session):
    1. Supersede any existing active decision for this member.
    2. Insert the new decision.
    3. Insert condition exclusions.
    4. Sync denormalised fields on Member (waiting_period_end_date, late_joiner_penalty_pct).
    All four writes are in the same SQLAlchemy session; get_db commits on success
    or rolls back on any exception.
    """
    # Step 1: supersede existing active decision
    existing_result = await db.execute(
        select(UnderwritingDecision).where(
            UnderwritingDecision.member_id == data.member_id,
            UnderwritingDecision.scheme_id == scheme_id,
            UnderwritingDecision.status == "active",
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        existing.status = "superseded"
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Step 2: resolve lifecycle status
    if data.decision in ACTIVE_DECISIONS:
        lifecycle_status = "active"
    else:
        lifecycle_status = data.decision  # "referred" or "denied"

    # Step 3: create new decision
    decision = UnderwritingDecision(
        scheme_id=scheme_id,
        member_id=data.member_id,
        decision_date=data.decision_date,
        effective_date=data.effective_date,
        decision=data.decision,
        status=lifecycle_status,
        has_prior_cover=data.has_prior_cover,
        prior_cover_years=data.prior_cover_years,
        prior_cover_break_days=data.prior_cover_break_days,
        prior_cover_proof_type=data.prior_cover_proof_type,
        prior_cover_schemes_json=data.prior_cover_schemes_json,
        general_wp_months=data.general_wp_months,
        general_wp_end_date=data.general_wp_end_date,
        is_late_joiner=data.is_late_joiner,
        late_joiner_uncovered_years=data.late_joiner_uncovered_years,
        late_joiner_penalty_pct=data.late_joiner_penalty_pct,
        base_monthly_contribution=data.base_monthly_contribution,
        total_monthly_contribution=data.total_monthly_contribution,
        created_by=created_by,
        notes=data.notes,
    )
    db.add(decision)
    await db.flush()  # get decision.id before creating exclusions

    # Step 4: condition exclusions
    for excl in data.condition_exclusions:
        ce = MemberConditionExclusion(
            underwriting_decision_id=decision.id,
            member_id=data.member_id,
            scheme_id=scheme_id,
            icd10_code=excl.icd10_code,
            condition_name=excl.condition_name,
            is_pmb=excl.is_pmb,
            exclusion_start_date=excl.exclusion_start_date,
            exclusion_end_date=excl.exclusion_end_date,
        )
        db.add(ce)

    # Step 5: sync member denormalised fields and activate for active decisions
    if lifecycle_status == "active":
        member_result = await db.execute(
            select(Member).where(Member.id == data.member_id)
        )
        member = member_result.scalar_one_or_none()
        if member:
            member.waiting_period_end_date = data.general_wp_end_date
            member.late_joiner_penalty_pct = data.late_joiner_penalty_pct
            member.status = "active"
            member.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()

    # Reload with relationships for the response
    result = await db.execute(
        select(UnderwritingDecision)
        .where(UnderwritingDecision.id == decision.id)
        .options(selectinload(UnderwritingDecision.condition_exclusions))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Two-gate auto-underwriting engine
# ---------------------------------------------------------------------------

# Gate 1: newborn threshold — babies ≤ 90 days old at enrollment are exempt
NEWBORN_THRESHOLD_DAYS = 90

# MSA: conditions exclusions run for 12 months from the effective date
CONDITION_EXCLUSION_MONTHS = 12


def _is_newborn(date_of_birth: date, effective_date: date) -> bool:
    age_days = (effective_date - date_of_birth).days
    return 0 <= age_days <= NEWBORN_THRESHOLD_DAYS


def _gate1_underwriting_required(
    join_reason: str,
    date_of_birth: Optional[date],
    effective_date: date,
) -> bool:
    """Gate 1: Return True if underwriting is required, False if member is exempt.

    Exempt cases (auto-approve without waiting period):
    - Newborn ≤ 90 days at effective_date
    - Dependant becoming principal (already underwritten as a dependant)
    """
    if join_reason == "dependant_becoming_principal":
        return False
    if date_of_birth is not None and _is_newborn(date_of_birth, effective_date):
        return False
    return True


async def evaluate_enrollment(
    db: AsyncSession,
    questionnaire: EnrollmentQuestionnaire,
    member: Member,
    scheme_id: int,
    created_by: int,
) -> UnderwritingDecision:
    """Gate 1 + Gate 2: evaluate an enrollment questionnaire and produce a decision.

    Gate 1 — is underwriting required?
      - Exempt: newborn or dependant becoming principal → auto-approve, no WP.

    Gate 2 — compute the decision:
      - conditions_declared=True → "conditionally_approved" + condition exclusions
      - Otherwise → "approved"
      - WP and late-joiner penalty always computed from MSA rules.
    """
    today = date.today()
    effective_date = member.join_date or today

    # Gate 1 check
    underwriting_required = _gate1_underwriting_required(
        join_reason=questionnaire.join_reason,
        date_of_birth=member.date_of_birth,
        effective_date=effective_date,
    )

    if not underwriting_required:
        # Exempt — auto-approve with no waiting period, no penalty
        preview = UnderwritingPreviewResponse(
            general_wp_months=0,
            general_wp_end_date=None,
            is_late_joiner=False,
            late_joiner_penalty_pct=0,
            total_monthly_contribution=None,
        )
        engine_decision = "approved"
        condition_exclusions = []
    else:
        # Gate 2 — compute WP + penalty
        preview = compute_wp_and_penalty(
            effective_date=effective_date,
            has_prior_cover=questionnaire.has_prior_cover,
            prior_cover_break_days=questionnaire.prior_cover_break_days,
            is_late_joiner=questionnaire.is_late_joiner,
            late_joiner_uncovered_years=questionnaire.late_joiner_uncovered_years,
        )

        # Determine outcome
        if questionnaire.conditions_declared and questionnaire.declared_conditions_json:
            engine_decision = "conditionally_approved"
            condition_exclusions = [
                MemberConditionExclusionCreate(
                    icd10_code=c["icd10_code"],
                    condition_name=c.get("condition_name"),
                    is_pmb=False,  # auto-engine does not classify PMB; reviewer can override
                    exclusion_start_date=effective_date,
                    exclusion_end_date=_add_months(effective_date, CONDITION_EXCLUSION_MONTHS),
                )
                for c in questionnaire.declared_conditions_json
            ]
        else:
            engine_decision = "approved"
            condition_exclusions = []

    create_data = UnderwritingDecisionCreate(
        member_id=questionnaire.member_id,
        decision_date=today,
        effective_date=effective_date,
        decision=engine_decision,
        has_prior_cover=questionnaire.has_prior_cover,
        prior_cover_years=float(questionnaire.prior_cover_years) if questionnaire.prior_cover_years else None,
        prior_cover_break_days=questionnaire.prior_cover_break_days,
        prior_cover_proof_type=questionnaire.prior_cover_proof_type,
        prior_cover_schemes_json=questionnaire.prior_cover_schemes_json,
        general_wp_months=preview.general_wp_months,
        general_wp_end_date=preview.general_wp_end_date,
        is_late_joiner=preview.is_late_joiner,
        late_joiner_uncovered_years=questionnaire.late_joiner_uncovered_years,
        late_joiner_penalty_pct=preview.late_joiner_penalty_pct,
        total_monthly_contribution=preview.total_monthly_contribution,
        notes=f"Auto-generated by enrollment engine v1. Join reason: {questionnaire.join_reason}.",
        condition_exclusions=condition_exclusions,
    )

    decision = await create_decision(db, create_data, scheme_id, created_by)

    # Mark questionnaire as processed and link to decision
    questionnaire.status = "processed"
    questionnaire.underwriting_decision_id = decision.id
    questionnaire.engine_outcome = engine_decision
    await db.commit()

    return decision


async def process_questionnaire(
    db: AsyncSession,
    data: EnrollmentQuestionnaireCreate,
    scheme_id: int,
    created_by: int,
) -> tuple[EnrollmentQuestionnaire, UnderwritingDecision]:
    """Persist the questionnaire and immediately evaluate it.

    Returns (questionnaire, decision).
    """
    # Fetch the member to access DOB and join_date for gate evaluation
    member_result = await db.execute(select(Member).where(Member.id == data.member_id))
    member = member_result.scalar_one_or_none()
    if not member:
        raise ValueError(f"Member {data.member_id} not found")

    # Persist questionnaire
    q = EnrollmentQuestionnaire(
        member_id=data.member_id,
        scheme_id=scheme_id,
        join_reason=data.join_reason,
        has_prior_cover=data.has_prior_cover,
        prior_cover_years=data.prior_cover_years,
        prior_cover_break_days=data.prior_cover_break_days,
        prior_cover_proof_type=data.prior_cover_proof_type,
        prior_cover_schemes_json=data.prior_cover_schemes_json,
        is_late_joiner=data.is_late_joiner,
        late_joiner_uncovered_years=data.late_joiner_uncovered_years,
        conditions_declared=data.conditions_declared,
        declared_conditions_json=[
            {"icd10_code": c.icd10_code, "condition_name": c.condition_name}
            for c in (data.declared_conditions_json or [])
        ] if data.declared_conditions_json else None,
        completed_by=created_by,
        status="pending",
    )
    db.add(q)
    await db.flush()  # get q.id

    # Evaluate gates and produce decision
    decision = await evaluate_enrollment(db, q, member, scheme_id, created_by)

    return q, decision
