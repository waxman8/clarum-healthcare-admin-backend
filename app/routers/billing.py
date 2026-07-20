from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from sqlalchemy.orm import selectinload
from typing import Optional
import math
import json
from datetime import date, datetime, timezone

from app.database import get_db
from app.models.billing import Formulary, NappiCode, MemberContribution, ContributionRate
from app.models.members import Member, Dependant
from app.schemas.billing import (
    ContributionCalculatorRequest,
    ContributionCalculatorResponse,
    FormularyEntryResponse,
    PaginatedFormularyResponse,
    BillingRunRequest,
    BillingRunResponse,
    MemberContributionResponse,
    PaymentRecordRequest,
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.constants import Role
from app.services.contribution_calculator import calculate_monthly_contribution
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.post("/calculate-contribution", response_model=ContributionCalculatorResponse)
async def calculate_contribution(
    request: ContributionCalculatorRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate monthly contribution for a given plan and family composition.
    No authentication required — used for public quotation.
    """
    result = await calculate_monthly_contribution(
        db=db,
        plan_option_id=request.plan_option_id,
        adult_dependants=request.adult_dependants,
        children=request.children,
        benefit_year=request.benefit_year,
    )
    return ContributionCalculatorResponse(**result)


@router.get("/formulary", response_model=PaginatedFormularyResponse)
async def list_formulary(
    plan_option_id: int = Query(..., description="Filter by plan option"),
    formulary_type: Optional[str] = Query(None, description="CHRONIC | ACUTE | ONCOLOGY | RADIOLOGY | PATHOLOGY"),
    cdl_condition: Optional[str] = Query(None, description="Filter by CDL condition name"),
    search: Optional[str] = Query(None, description="Search by product or generic name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return formulary entries for a plan, paginated."""
    query = (
        select(Formulary)
        .options(selectinload(Formulary.nappi))
        .where(Formulary.plan_option_id == plan_option_id)
    )
    if formulary_type:
        query = query.where(Formulary.formulary_type == formulary_type)
    if cdl_condition:
        query = query.where(Formulary.cdl_condition == cdl_condition)
    if search:
        query = query.join(NappiCode, Formulary.nappi_code_id == NappiCode.id, isouter=True).where(
            NappiCode.product_name.ilike(f"%{search}%")
            | NappiCode.generic_name.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    entries = result.scalars().all()

    items = []
    for entry in entries:
        items.append(
            FormularyEntryResponse(
                id=entry.id,
                plan_option_id=entry.plan_option_id,
                formulary_type=entry.formulary_type,
                cdl_condition=entry.cdl_condition,
                nappi_code=entry.nappi.nappi_code if entry.nappi else None,
                product_name=entry.nappi.product_name if entry.nappi else None,
                generic_name=entry.nappi.generic_name if entry.nappi else None,
                is_covered=entry.is_covered,
                is_preferred=entry.is_preferred,
                reference_price_cents=entry.reference_price_cents,
                max_quantity_per_script=entry.max_quantity_per_script,
                copayment_if_non_formulary_pct=entry.copayment_if_non_formulary_pct,
                effective_year=entry.effective_year,
            )
        )

    return PaginatedFormularyResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


# --------------- Contribution Ledger ---------------

ADULT_RELATIONSHIPS = {"spouse", "life_partner", "adult_dependant", "disabled_dependant"}
CHILD_RELATIONSHIPS = {"child", "student"}


def _contribution_to_dict(c: MemberContribution) -> dict:
    return {
        "id": c.id,
        "member_id": c.member_id,
        "scheme_id": c.scheme_id,
        "billing_month": c.billing_month.strftime("%Y-%m"),
        "principal_cents": c.principal_cents,
        "adult_dependant_count": c.adult_dependant_count,
        "adult_dependant_cents": c.adult_dependant_cents,
        "child_count": c.child_count,
        "child_cents": c.child_cents,
        "child_cap_applied": c.child_cap_applied,
        "late_joiner_penalty_pct": c.late_joiner_penalty_pct,
        "late_joiner_surcharge_cents": c.late_joiner_surcharge_cents,
        "amount_due_cents": c.amount_due_cents,
        "amount_paid_cents": c.amount_paid_cents,
        "payment_date": c.payment_date.isoformat() if c.payment_date else None,
        "payment_reference": c.payment_reference,
        "status": c.status,
        "generated_at": c.generated_at.isoformat() if c.generated_at else None,
    }


@router.post("/generate-contributions", response_model=BillingRunResponse)
async def generate_contributions(
    request: BillingRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate contribution ledger entries for all active members for a billing month."""
    if current_user.role not in [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can run billing")

    # Parse billing month
    try:
        parts = request.billing_month.split("-")
        billing_date = date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="billing_month must be YYYY-MM format")

    sid = _effective_scheme_id(current_user)

    # Load active members in scheme with dependants eagerly loaded
    member_query = (
        select(Member)
        .options(selectinload(Member.dependants))
        .where(Member.status == "active")
    )
    if sid is not None:
        member_query = member_query.where(Member.scheme_id == sid)
    members_result = await db.execute(member_query)
    active_members = members_result.scalars().all()

    if not active_members:
        return BillingRunResponse(generated=0, skipped=0, total_active=0)

    # Find which members already have an entry for this month
    existing_result = await db.execute(
        select(MemberContribution.member_id).where(
            MemberContribution.billing_month == billing_date,
        )
    )
    existing_ids = set(existing_result.scalars().all())

    # Cache contribution rates for all plans in the scheme for the benefit year
    plan_ids = {m.plan_option_id for m in active_members}
    rates_query = select(ContributionRate).where(
        ContributionRate.plan_option_id.in_(plan_ids),
        ContributionRate.effective_year == billing_date.year,
    )
    rates_result = await db.execute(rates_query)
    rates_by_plan = {}
    for r in rates_result.scalars().all():
        if r.plan_option_id not in rates_by_plan:
            rates_by_plan[r.plan_option_id] = {}
        rates_by_plan[r.plan_option_id][r.member_type] = r.monthly_rate_cents

    generated = 0
    skipped = 0
    new_contributions = []

    for member in active_members:
        if member.id in existing_ids:
            skipped += 1
            continue

        # Use eagerly loaded dependants
        deps = [d for d in member.dependants if d.status == "active"]
        adult_count = sum(1 for d in deps if d.dependant_relationship in ADULT_RELATIONSHIPS)
        child_count = sum(1 for d in deps if d.dependant_relationship in CHILD_RELATIONSHIPS)

        # Calculate contribution using cached rates
        plan_rates = rates_by_plan.get(member.plan_option_id)
        if not plan_rates:
            continue

        calc = await calculate_monthly_contribution(
            db=db,
            plan_option_id=member.plan_option_id,
            adult_dependants=adult_count,
            children=child_count,
            benefit_year=billing_date.year,
            prefetched_rates=plan_rates,
        )

        if calc.get("error"):
            continue

        # Extract line amounts
        principal_cents = 0
        adult_dep_cents = 0
        child_cents = 0
        for line in calc.get("lines", []):
            if line["member_type"] == "PRINCIPAL":
                principal_cents = line["subtotal_cents"]
            elif line["member_type"] == "ADULT_DEPENDANT":
                adult_dep_cents = line["subtotal_cents"]
            elif line["member_type"] == "CHILD":
                child_cents = line["subtotal_cents"]

        base_total = calc["total_monthly_cents"]

        # Apply late-joiner penalty
        ljp_pct = member.late_joiner_penalty_pct or 0
        ljp_surcharge = round(base_total * ljp_pct / 100)
        amount_due = base_total + ljp_surcharge

        new_contributions.append(
            MemberContribution(
                member_id=member.id,
                scheme_id=member.scheme_id,
                billing_month=billing_date,
                principal_cents=principal_cents,
                adult_dependant_count=adult_count,
                adult_dependant_cents=adult_dep_cents,
                child_count=child_count,
                child_cents=child_cents,
                child_cap_applied=calc.get("child_cap_applied", False),
                late_joiner_penalty_pct=ljp_pct,
                late_joiner_surcharge_cents=ljp_surcharge,
                amount_due_cents=amount_due,
                status="generated",
            )
        )
        generated += 1

    if new_contributions:
        db.add_all(new_contributions)
        log_audit(
            db, "member_contribution", None, "generate_batch",
            user_id=current_user.id, user_role=current_user.role,
            scheme_id=sid, entity_label=f"{request.billing_month} ({generated} members)",
            new_value=json.dumps({"billing_month": request.billing_month, "generated": generated, "skipped": skipped}, default=str),
        )
        await db.commit()
    else:
        await db.flush()

    return BillingRunResponse(
        generated=generated,
        skipped=skipped,
        total_active=len(active_members),
    )


@router.get("/contributions")
async def list_contributions(
    billing_month: Optional[str] = Query(None, description="Filter by YYYY-MM"),
    status: Optional[str] = Query(None),
    member_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contribution ledger entries. Paginated and filterable."""
    sid = _effective_scheme_id(current_user)
    query = select(MemberContribution)
    if sid is not None:
        query = query.where(MemberContribution.scheme_id == sid)
    if billing_month:
        parts = billing_month.split("-")
        bm = date(int(parts[0]), int(parts[1]), 1)
        query = query.where(MemberContribution.billing_month == bm)
    if status:
        query = query.where(MemberContribution.status == status)
    if member_id:
        query = query.where(MemberContribution.member_id == member_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.order_by(MemberContribution.billing_month.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "items": [_contribution_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 1,
    }


@router.patch("/contributions/{contribution_id}/payment")
async def record_payment(
    contribution_id: int,
    payment: PaymentRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a payment against a contribution ledger entry."""
    if current_user.role not in [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can record payments")

    result = await db.execute(
        select(MemberContribution).where(MemberContribution.id == contribution_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Contribution entry not found")

    # Enforce scheme scoping
    sid = _effective_scheme_id(current_user)
    if sid is not None and entry.scheme_id != sid:
        raise HTTPException(status_code=404, detail="Contribution entry not found")

    old_status = entry.status
    entry.amount_paid_cents = payment.amount_paid_cents
    entry.payment_date = date.fromisoformat(payment.payment_date)
    entry.payment_reference = payment.payment_reference
    entry.updated_at = datetime.now(timezone.utc)
    entry.modified_date = datetime.now(timezone.utc)
    entry.modified_user = current_user.id

    if entry.amount_paid_cents >= entry.amount_due_cents:
        entry.status = "paid"
    elif entry.amount_paid_cents > 0:
        entry.status = "partially_paid"

    log_audit(
        db, "member_contribution", entry.id, "record_payment",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=entry.scheme_id, entity_label=entry.billing_month.strftime("%Y-%m"),
        old_value=json.dumps({"status": old_status}, default=str),
        new_value=json.dumps({"amount_paid_cents": payment.amount_paid_cents, "status": entry.status}, default=str),
    )
    await db.commit()
    await db.refresh(entry)

    return _contribution_to_dict(entry)
