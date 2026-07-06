"""Contribution calculator service.

Reads all rates from the contribution_rates table — nothing hardcoded.
The CHILD_CAP constant (3) is the only exception: it is a statutory rule
defined in the Medical Schemes Act, not a scheme-configurable value.
"""
from datetime import date
from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import ContributionRate
from app.models.reference import PlanOption

# MSA statutory cap: maximum 3 children billed at child rate per principal.
# 4th child and beyond are covered at no additional charge.
CHILD_CAP = 3


async def calculate_monthly_contribution(
    db: AsyncSession,
    plan_option_id: int,
    adult_dependants: int,
    children: int,
    benefit_year: int,
    prefetched_rates: Optional[Dict] = None,
) -> dict:
    """
    Calculate total monthly contribution for a family composition.

    Returns a breakdown dict with per-type lines and grand total.
    All monetary values are in cents.

    Args:
        plan_option_id: PlanOption.id (scheme-scoped)
        adult_dependants: count of adult dependants (spouse, life partner, adult child 21+)
        children: count of children (under 21, or students under 28 full-time)
        benefit_year: year for rate lookup (e.g. 2026)
    """
    # Load rates for this plan × year
    if prefetched_rates is not None:
        rates = prefetched_rates
    else:
        result = await db.execute(
            select(ContributionRate).where(
                ContributionRate.plan_option_id == plan_option_id,
                ContributionRate.effective_year == benefit_year,
            )
        )
        rates_list = result.scalars().all()
        rates = {r.member_type: r.monthly_rate_cents for r in rates_list}

    if not rates:
        # No contribution rates configured for this plan/year
        return {
            "error": f"No contribution rates found for plan_option_id={plan_option_id} "
                     f"benefit_year={benefit_year}",
            "lines": [],
            "total_monthly_cents": 0,
            "child_cap_applied": False,
            "children_billed": 0,
        }

    # Apply 3-child cap
    children_billed = min(children, CHILD_CAP)
    children_free = max(0, children - CHILD_CAP)
    child_cap_applied = children > CHILD_CAP

    lines = []
    total = 0

    for member_type, count in [
        ("PRINCIPAL", 1),
        ("ADULT_DEPENDANT", adult_dependants),
        ("CHILD", children_billed),
    ]:
        if count == 0:
            continue
        rate = rates.get(member_type, 0)
        subtotal = rate * count
        lines.append({
            "member_type": member_type,
            "count": count,
            "rate_cents": rate,
            "subtotal_cents": subtotal,
        })
        total += subtotal

    # Free children row (informational — R0 charge)
    if children_free > 0:
        lines.append({
            "member_type": "CHILD_FREE",
            "count": children_free,
            "rate_cents": 0,
            "subtotal_cents": 0,
        })

    return {
        "lines": lines,
        "total_monthly_cents": total,
        "child_cap_applied": child_cap_applied,
        "children_billed": children_billed,
        "children_free": children_free,
    }


async def get_plan_options_for_scheme(
    db: AsyncSession,
    scheme_id: int,
) -> list[PlanOption]:
    """Return all active plan options for a scheme."""
    result = await db.execute(
        select(PlanOption).where(
            PlanOption.scheme_id == scheme_id,
            PlanOption.is_active == True,  # noqa: E712
        ).order_by(PlanOption.monthly_premium)
    )
    return result.scalars().all()
