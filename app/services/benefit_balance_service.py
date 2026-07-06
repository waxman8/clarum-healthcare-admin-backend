"""Benefit balance service.

Manages the per-member, per-category, per-year running benefit balances.

Design:
- benefit_limits = plan-level TEMPLATE (what the plan allows)
- benefit_balances = per-member RUNNING COUNTER (what this member has used)

These are two separate concerns. The engine reads benefit_balances for limit checks;
benefit_limits is only consulted at initialisation time (enrolment / 1 Jan reset).
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BenefitBalance
from app.models.members import BenefitLimit


async def initialise_benefit_balances(
    db: AsyncSession,
    member_id: int,
    scheme_id: int,
    plan_option_id: int,
    benefit_year: int,
) -> int:
    """
    Create BenefitBalance rows for a member for the given benefit year.
    Reads limits from the benefit_limits table for the plan.
    Idempotent: skips categories that already have a balance row.

    Returns the count of rows created.
    """
    # Load all limits for this plan/year
    limits_result = await db.execute(
        select(BenefitLimit).where(
            BenefitLimit.plan_option_id == plan_option_id,
            BenefitLimit.benefit_year == benefit_year,
        )
    )
    limits = limits_result.scalars().all()

    # Load existing balances to skip duplicates
    existing_result = await db.execute(
        select(BenefitBalance.benefit_category).where(
            BenefitBalance.member_id == member_id,
            BenefitBalance.benefit_year == benefit_year,
        )
    )
    existing_categories = {row[0] for row in existing_result.all()}

    created = 0
    for limit in limits:
        if limit.benefit_category in existing_categories:
            continue

        # UNLIMITED limits don't need a balance tracker — adjudication always passes
        if limit.limit_type == "UNLIMITED":
            continue

        opening = limit.limit_value if limit.limit_type in ("RAND", "VISITS") else 0

        balance = BenefitBalance(
            member_id=member_id,
            scheme_id=scheme_id,
            benefit_category=limit.benefit_category,
            benefit_year=benefit_year,
            opening_balance_cents=opening,
            used_cents=0,
            reserved_cents=0,
            visits_used=0,
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(balance)
        created += 1

    await db.flush()
    return created


async def get_benefit_balance(
    db: AsyncSession,
    member_id: int,
    benefit_category: str,
    benefit_year: int,
) -> Optional[BenefitBalance]:
    """Return the BenefitBalance row for a member/category/year, or None."""
    result = await db.execute(
        select(BenefitBalance).where(
            and_(
                BenefitBalance.member_id == member_id,
                BenefitBalance.benefit_category == benefit_category,
                BenefitBalance.benefit_year == benefit_year,
            )
        )
    )
    return result.scalar_one_or_none()


async def get_available_balance(
    db: AsyncSession,
    member_id: int,
    benefit_category: str,
    benefit_year: int,
) -> int:
    """
    Return available balance in cents.
    Returns 999_999_999 (effectively unlimited) if no balance row exists.
    """
    balance = await get_benefit_balance(db, member_id, benefit_category, benefit_year)
    if balance is None:
        return 999_999_999  # No tracking = unlimited for this category/member
    return max(0, balance.opening_balance_cents - balance.used_cents - balance.reserved_cents)


async def decrement_benefit_balance(
    db: AsyncSession,
    member_id: int,
    benefit_category: str,
    benefit_year: int,
    amount_cents: int,
) -> Optional[BenefitBalance]:
    """
    Increment used_cents by amount_cents for a balance row.
    No-op if no balance row exists (unlimited benefit).
    Returns the updated row or None.
    """
    balance = await get_benefit_balance(db, member_id, benefit_category, benefit_year)
    if balance is None:
        return None

    balance.used_cents = (balance.used_cents or 0) + amount_cents
    balance.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return balance


async def reserve_benefit_balance(
    db: AsyncSession,
    member_id: int,
    benefit_category: str,
    benefit_year: int,
    amount_cents: int,
) -> Optional[BenefitBalance]:
    """
    Reserve an amount against benefit balance (for in-flight authorisations).
    Does not deduct from used_cents — use decrement_benefit_balance when the claim settles.
    """
    balance = await get_benefit_balance(db, member_id, benefit_category, benefit_year)
    if balance is None:
        return None

    balance.reserved_cents = (balance.reserved_cents or 0) + amount_cents
    balance.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return balance


async def get_all_balances_for_member(
    db: AsyncSession,
    member_id: int,
    benefit_year: int,
) -> list[BenefitBalance]:
    """Return all BenefitBalance rows for a member in a given year."""
    result = await db.execute(
        select(BenefitBalance).where(
            BenefitBalance.member_id == member_id,
            BenefitBalance.benefit_year == benefit_year,
        ).order_by(BenefitBalance.benefit_category)
    )
    return result.scalars().all()
