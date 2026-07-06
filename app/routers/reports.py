"""CMS compliance and scheme management reports."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.claims import Claim, ClaimLine
from app.models.billing import ChronicRegistration, BenefitBalance
from app.models.members import Member
from app.models.reference import ICD10Code
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def scheme_filter_value(current_user: User):
    return _effective_scheme_id(current_user)


@router.get("/pmb")
async def pmb_funding_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    CMS PMB funding analysis.
    Returns total claimed, approved, and scheme-funded amounts for PMB lines,
    broken down by benefit bucket (PMB_RISK vs MEMBER_LIABILITY vs overrides).
    """
    scheme_id = scheme_filter_value(current_user)

    query = select(
        ClaimLine.benefit_bucket,
        func.count(ClaimLine.id).label("line_count"),
        func.sum(ClaimLine.billed_amount).label("total_billed"),
        func.sum(ClaimLine.approved_amount).label("total_approved"),
        func.sum(ClaimLine.copayment_cents).label("total_copayment"),
        func.sum(ClaimLine.member_liability).label("total_member_liability"),
    ).join(Claim, ClaimLine.claim_id == Claim.id).where(
        ClaimLine.is_pmb_line == True  # noqa: E712
    )

    if scheme_id is not None:
        query = query.where(Claim.scheme_id == scheme_id)
    if date_from:
        query = query.where(Claim.date_of_service_from >= date_from)
    if date_to:
        query = query.where(Claim.date_of_service_to <= date_to)

    query = query.group_by(ClaimLine.benefit_bucket)
    result = await db.execute(query)
    rows = result.mappings().all()

    # Total PMB risk funding
    total_query = select(
        func.sum(ClaimLine.approved_amount).label("total_pmb_funded"),
        func.count(ClaimLine.id).label("total_pmb_lines"),
    ).join(Claim, ClaimLine.claim_id == Claim.id).where(
        ClaimLine.is_pmb_line == True  # noqa: E712
    )
    if scheme_id is not None:
        total_query = total_query.where(Claim.scheme_id == scheme_id)
    if date_from:
        total_query = total_query.where(Claim.date_of_service_from >= date_from)
    if date_to:
        total_query = total_query.where(Claim.date_of_service_to <= date_to)
    total_result = await db.execute(total_query)
    totals = total_result.mappings().one_or_none()

    return {
        "period": {"from": str(date_from) if date_from else None, "to": str(date_to) if date_to else None},
        "breakdown_by_bucket": [dict(r) for r in rows],
        "totals": dict(totals) if totals else {"total_pmb_funded": 0, "total_pmb_lines": 0},
    }


@router.get("/rejections")
async def rejections_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rejection rates by rejection_reason_code.
    Returns frequency and total billed for each rejection code.
    """
    scheme_id = scheme_filter_value(current_user)

    query = select(
        ClaimLine.rejection_reason_code,
        func.count(ClaimLine.id).label("rejection_count"),
        func.sum(ClaimLine.billed_amount).label("total_billed_rejected"),
    ).join(Claim, ClaimLine.claim_id == Claim.id).where(
        ClaimLine.rejection_reason_code.isnot(None)
    )

    if scheme_id is not None:
        query = query.where(Claim.scheme_id == scheme_id)
    if date_from:
        query = query.where(Claim.date_of_service_from >= date_from)
    if date_to:
        query = query.where(Claim.date_of_service_to <= date_to)

    query = query.group_by(ClaimLine.rejection_reason_code).order_by(
        func.count(ClaimLine.id).desc()
    )
    result = await db.execute(query)
    rows = result.mappings().all()

    total_lines_query = select(func.count(ClaimLine.id)).join(Claim, ClaimLine.claim_id == Claim.id)
    if scheme_id is not None:
        total_lines_query = total_lines_query.where(Claim.scheme_id == scheme_id)
    if date_from:
        total_lines_query = total_lines_query.where(Claim.date_of_service_from >= date_from)
    if date_to:
        total_lines_query = total_lines_query.where(Claim.date_of_service_to <= date_to)
    total_lines = (await db.execute(total_lines_query)).scalar() or 1

    return {
        "period": {"from": str(date_from) if date_from else None, "to": str(date_to) if date_to else None},
        "rejection_codes": [
            {**dict(r), "rejection_rate_pct": round(r["rejection_count"] / total_lines * 100, 2)}
            for r in rows
        ],
        "total_claim_lines": total_lines,
    }


@router.get("/chronic-coverage")
async def chronic_coverage_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    CDL registrations grouped by condition name and status.
    Useful for CMS chronic condition penetration reporting.
    """
    scheme_id = scheme_filter_value(current_user)

    query = select(
        ICD10Code.cdl_condition_name,
        ChronicRegistration.status,
        func.count(ChronicRegistration.id).label("count"),
    ).join(ICD10Code, ChronicRegistration.icd10_code_id == ICD10Code.id)

    if scheme_id is not None:
        query = query.where(ChronicRegistration.scheme_id == scheme_id)

    query = query.group_by(ICD10Code.cdl_condition_name, ChronicRegistration.status).order_by(
        ICD10Code.cdl_condition_name, ChronicRegistration.status
    )
    result = await db.execute(query)
    rows = result.mappings().all()

    # Pivot into condition → {PENDING, APPROVED, DECLINED} counts
    conditions: dict = {}
    for row in rows:
        cond = row["cdl_condition_name"] or "UNKNOWN"
        if cond not in conditions:
            conditions[cond] = {"condition": cond, "PENDING": 0, "APPROVED": 0, "DECLINED": 0, "EXPIRED": 0}
        conditions[cond][row["status"]] = row["count"]

    return {
        "conditions": list(conditions.values()),
        "total_registrations": sum(
            c["PENDING"] + c["APPROVED"] + c["DECLINED"] + c["EXPIRED"]
            for c in conditions.values()
        ),
    }


@router.get("/benefit-exhaustion")
async def benefit_exhaustion_report(
    benefit_year: int = Query(..., description="Benefit year to check"),
    threshold_pct: int = Query(80, ge=1, le=100, description="Exhaustion threshold percentage"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Members where used benefit exceeds threshold_pct% of opening balance.
    Useful for proactive member management before year-end benefit depletion.
    """
    scheme_id = scheme_filter_value(current_user)

    query = select(
        BenefitBalance.member_id,
        Member.first_name,
        Member.surname,
        Member.membership_number,
        BenefitBalance.benefit_category,
        BenefitBalance.opening_balance_cents,
        BenefitBalance.used_cents,
        BenefitBalance.reserved_cents,
    ).join(Member, BenefitBalance.member_id == Member.id).where(
        BenefitBalance.benefit_year == benefit_year,
        BenefitBalance.opening_balance_cents > 0,
    )

    if scheme_id is not None:
        query = query.where(BenefitBalance.scheme_id == scheme_id)

    result = await db.execute(query)
    rows = result.mappings().all()

    exhausted = []
    for row in rows:
        opening = row["opening_balance_cents"]
        used = (row["used_cents"] or 0) + (row["reserved_cents"] or 0)
        pct_used = round(used / opening * 100, 1) if opening > 0 else 0
        if pct_used >= threshold_pct:
            exhausted.append({
                "member_id": row["member_id"],
                "member_name": f"{row['first_name']} {row['surname']}",
                "membership_number": row["membership_number"],
                "benefit_category": row["benefit_category"],
                "opening_balance_cents": opening,
                "used_cents": used,
                "available_cents": max(0, opening - used),
                "pct_used": pct_used,
            })

    exhausted.sort(key=lambda x: x["pct_used"], reverse=True)

    return {
        "benefit_year": benefit_year,
        "threshold_pct": threshold_pct,
        "members_at_risk": len(exhausted),
        "entries": exhausted,
    }
