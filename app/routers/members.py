from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
import math
import json
from datetime import datetime, timezone, date


from app.database import get_db
from app.models.members import Member, Dependant, BenefitLimit, MemberStatusHistory
from app.models.billing import BenefitBalance
from app.models.auth import User, Scheme
from app.schemas.members import (
    MemberCreate, MemberUpdate, MemberStatusUpdate, MemberResponse,
    DependantCreate, DependantUpdate, DependantResponse, BenefitLimitResponse,
    MemberStatusHistoryResponse, MemberSearchRequest, PaginatedMembersResponse,
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.billing import MemberContribution
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/members", tags=["members"])


def scheme_filter(query, current_user: User, model=Member):
    """Apply scheme_id filter when the user is scoped to a scheme."""
    sid = _effective_scheme_id(current_user)
    if sid is not None:
        query = query.where(model.scheme_id == sid)
    return query


async def get_scheme_for_user(db: AsyncSession, current_user: User) -> Scheme:
    """Return the user's scheme; raises if not found."""
    sid = _effective_scheme_id(current_user)
    result = await db.execute(select(Scheme).where(Scheme.id == sid))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=400, detail="User scheme not found")
    return scheme


async def get_member_scoped(member_id: int, db: AsyncSession, current_user: User) -> Member:
    """Fetch a member, enforcing scheme scoping."""
    sid = _effective_scheme_id(current_user)
    query = select(Member).where(Member.id == member_id)
    if sid is not None:
        query = query.where(Member.scheme_id == sid)
    result = await db.execute(query)
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.post("", response_model=MemberResponse)
async def create_member(
    member_data: MemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scheme = await get_scheme_for_user(db, current_user)

    # Generate membership number scoped to this scheme
    count_result = await db.execute(
        select(func.count(Member.id)).where(Member.scheme_id == scheme.id)
    )
    count = count_result.scalar() + 1
    year = datetime.now().year
    membership_number = f"{scheme.code}-{year}-{count:06d}"

    member = Member(
        **member_data.model_dump(exclude={"scheme_id"}),
        scheme_id=scheme.id,
        membership_number=membership_number,
    )
    db.add(member)
    await db.flush()

    history = MemberStatusHistory(
        member_id=member.id,
        old_status=None,
        new_status=member_data.status,
        changed_by=current_user.id,
        reason="Initial enrolment",
    )
    db.add(history)
    log_audit(
        db, "member", member.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=scheme.id, entity_label=f"{member.first_name} {member.surname}",
        new_value=json.dumps({"membership_number": membership_number, "status": member_data.status}, default=str),
    )
    await db.commit()

    result = await db.execute(
        select(Member).where(Member.id == member.id).options(selectinload(Member.plan_option))
    )
    return result.scalar_one()


@router.get("", response_model=PaginatedMembersResponse)
async def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    plan_option_id: Optional[int] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Member).options(selectinload(Member.plan_option))
    query = scheme_filter(query, current_user)

    if status:
        query = query.where(Member.status == status)
    if plan_option_id:
        query = query.where(Member.plan_option_id == plan_option_id)
    if search:
        query = query.where(
            or_(
                Member.first_name.ilike(f"%{search}%"),
                Member.surname.ilike(f"%{search}%"),
                Member.membership_number.ilike(f"%{search}%"),
                Member.id_number.ilike(f"%{search}%"),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    members = result.scalars().all()

    return PaginatedMembersResponse(
        items=members,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{member_id}", response_model=MemberResponse)
async def get_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _effective_scheme_id(current_user)
    query = select(Member).where(Member.id == member_id).options(selectinload(Member.plan_option))
    if sid is not None:
        query = query.where(Member.scheme_id == sid)
    result = await db.execute(query)
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.patch("/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: int,
    member_data: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_member_scoped(member_id, db, current_user)

    changes = member_data.model_dump(exclude_unset=True)
    old_values = {field: getattr(member, field) for field in changes}
    for field, value in changes.items():
        setattr(member, field, value)

    member.updated_at = datetime.now(timezone.utc)
    member.modified_date = datetime.now(timezone.utc)
    member.modified_user = current_user.id

    if changes:
        log_audit(
            db, "member", member.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            scheme_id=member.scheme_id, entity_label=f"{member.first_name} {member.surname}",
            old_value=json.dumps(old_values, default=str),
            new_value=json.dumps(changes, default=str),
        )
    await db.commit()

    result = await db.execute(
        select(Member).where(Member.id == member_id).options(selectinload(Member.plan_option))
    )
    return result.scalar_one()


@router.post("/{member_id}/status", response_model=MemberResponse)
async def update_member_status(
    member_id: int,
    status_data: MemberStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_member_scoped(member_id, db, current_user)

    valid_statuses = ["active", "pending", "suspended", "lapsed", "cancelled"]
    if status_data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    old_status = member.status
    member.status = status_data.status
    member.updated_at = datetime.now(timezone.utc)
    member.modified_date = datetime.now(timezone.utc)
    member.modified_user = current_user.id

    history = MemberStatusHistory(
        member_id=member.id,
        old_status=old_status,
        new_status=status_data.status,
        changed_by=current_user.id,
        reason=status_data.reason,
    )
    db.add(history)
    log_audit(
        db, "member", member.id, "status_change",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=member.scheme_id, entity_label=f"{member.first_name} {member.surname}",
        old_value=json.dumps({"status": old_status}),
        new_value=json.dumps({"status": status_data.status, "reason": status_data.reason}),
        reason=status_data.reason,
    )
    await db.commit()

    result = await db.execute(
        select(Member).where(Member.id == member_id).options(selectinload(Member.plan_option))
    )
    return result.scalar_one()


@router.get("/{member_id}/dependants", response_model=list[DependantResponse])
async def get_dependants(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the member belongs to the user's scheme
    await get_member_scoped(member_id, db, current_user)
    result = await db.execute(select(Dependant).where(Dependant.member_id == member_id))
    return result.scalars().all()


@router.post("/{member_id}/dependants", response_model=DependantResponse)
async def add_dependant(
    member_id: int,
    dependant_data: DependantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_member_scoped(member_id, db, current_user)

    dependant = Dependant(member_id=member_id, **dependant_data.model_dump())
    db.add(dependant)
    await db.flush()
    log_audit(
        db, "dependant", dependant.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=member.scheme_id, entity_label=f"{dependant.first_name} {dependant.surname}",
        new_value=json.dumps({"dependant_relationship": dependant.dependant_relationship}, default=str),
    )
    await db.commit()
    await db.refresh(dependant)
    return dependant


@router.get("/{member_id}/dependants/{dependant_id}", response_model=DependantResponse)
async def get_dependant(
    member_id: int,
    dependant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_member_scoped(member_id, db, current_user)
    result = await db.execute(
        select(Dependant).where(Dependant.id == dependant_id, Dependant.member_id == member_id)
    )
    dependant = result.scalar_one_or_none()
    if not dependant:
        raise HTTPException(status_code=404, detail="Dependant not found")
    return dependant


@router.patch("/{member_id}/dependants/{dependant_id}", response_model=DependantResponse)
async def update_dependant(
    member_id: int,
    dependant_id: int,
    data: DependantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_member_scoped(member_id, db, current_user)
    result = await db.execute(
        select(Dependant).where(Dependant.id == dependant_id, Dependant.member_id == member_id)
    )
    dependant = result.scalar_one_or_none()
    if not dependant:
        raise HTTPException(status_code=404, detail="Dependant not found")

    changes = data.model_dump(exclude_unset=True)
    old_values = {field: getattr(dependant, field) for field in changes}
    for field, value in changes.items():
        setattr(dependant, field, value)

    dependant.modified_date = datetime.now(timezone.utc)
    dependant.modified_user = current_user.id

    if changes:
        log_audit(
            db, "dependant", dependant.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            scheme_id=member.scheme_id, entity_label=f"{dependant.first_name} {dependant.surname}",
            old_value=json.dumps(old_values, default=str),
            new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(dependant)
    return dependant


@router.get("/{member_id}/benefits", response_model=list[BenefitLimitResponse])
async def get_member_benefits(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_member_scoped(member_id, db, current_user)

    limits_result = await db.execute(
        select(BenefitLimit).where(
            BenefitLimit.plan_option_id == member.plan_option_id,
            BenefitLimit.benefit_year == datetime.now().year,
        )
    )
    return limits_result.scalars().all()


@router.get("/{member_id}/benefit-balance")
async def get_member_benefit_balance(
    member_id: int,
    benefit_year: Optional[int] = Query(None, description="Benefit year; defaults to current year"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return live running benefit balances for a member.
    Shows opening balance, used, reserved, and available per category.
    """
    member = await get_member_scoped(member_id, db, current_user)
    year = benefit_year or datetime.now().year

    result = await db.execute(
        select(BenefitBalance).where(
            BenefitBalance.member_id == member_id,
            BenefitBalance.benefit_year == year,
        ).order_by(BenefitBalance.benefit_category)
    )
    balances = result.scalars().all()

    return [
        {
            "id": b.id,
            "benefit_category": b.benefit_category,
            "benefit_year": b.benefit_year,
            "opening_balance_cents": b.opening_balance_cents,
            "used_cents": b.used_cents or 0,
            "reserved_cents": b.reserved_cents or 0,
            "available_cents": max(
                0,
                b.opening_balance_cents - (b.used_cents or 0) - (b.reserved_cents or 0),
            ),
            "pct_used": round(
                ((b.used_cents or 0) + (b.reserved_cents or 0))
                / b.opening_balance_cents
                * 100,
                1,
            ) if b.opening_balance_cents > 0 else 0,
            "last_updated": b.last_updated.isoformat() if b.last_updated else None,
        }
        for b in balances
    ]


@router.get("/{member_id}/history", response_model=list[MemberStatusHistoryResponse])
async def get_member_history(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_member_scoped(member_id, db, current_user)
    result = await db.execute(
        select(MemberStatusHistory)
        .where(MemberStatusHistory.member_id == member_id)
        .order_by(MemberStatusHistory.changed_at.desc())
    )
    return result.scalars().all()


@router.get("/{member_id}/contributions")
async def get_member_contributions(
    member_id: int,
    year: Optional[int] = Query(None, description="Year to show; defaults to current year"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return contribution ledger entries for a member for a given year, plus next collection."""
    await get_member_scoped(member_id, db, current_user)

    today = date.today()
    target_year = year or today.year

    # Query ledger entries for the requested year
    result = await db.execute(
        select(MemberContribution)
        .where(
            MemberContribution.member_id == member_id,
            func.extract("year", MemberContribution.billing_month) == target_year,
        )
        .order_by(MemberContribution.billing_month)
    )
    entries = result.scalars().all()

    def entry_to_dict(e):
        return {
            "id": e.id,
            "member_id": e.member_id,
            "scheme_id": e.scheme_id,
            "billing_month": e.billing_month.strftime("%Y-%m"),
            "principal_cents": e.principal_cents,
            "adult_dependant_count": e.adult_dependant_count,
            "adult_dependant_cents": e.adult_dependant_cents,
            "child_count": e.child_count,
            "child_cents": e.child_cents,
            "child_cap_applied": e.child_cap_applied,
            "late_joiner_penalty_pct": e.late_joiner_penalty_pct,
            "late_joiner_surcharge_cents": e.late_joiner_surcharge_cents,
            "amount_due_cents": e.amount_due_cents,
            "amount_paid_cents": e.amount_paid_cents,
            "payment_date": e.payment_date.isoformat() if e.payment_date else None,
            "payment_reference": e.payment_reference,
            "status": e.status,
            "generated_at": e.generated_at.isoformat() if e.generated_at else None,
        }

    months = [entry_to_dict(e) for e in entries]

    # Next collection: find the entry for next calendar month
    if today.month == 12:
        next_month_date = date(today.year + 1, 1, 1)
    else:
        next_month_date = date(today.year, today.month + 1, 1)

    next_result = await db.execute(
        select(MemberContribution).where(
            MemberContribution.member_id == member_id,
            MemberContribution.billing_month == next_month_date,
        )
    )
    next_entry = next_result.scalar_one_or_none()

    return {
        "months": months,
        "next_collection": entry_to_dict(next_entry) if next_entry else None,
    }


@router.post("/search", response_model=PaginatedMembersResponse)
async def search_members(
    search_request: MemberSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Member).options(selectinload(Member.plan_option))
    query = scheme_filter(query, current_user)

    if search_request.query:
        q = search_request.query
        query = query.where(
            or_(
                Member.first_name.ilike(f"%{q}%"),
                Member.surname.ilike(f"%{q}%"),
                Member.membership_number.ilike(f"%{q}%"),
                Member.id_number.ilike(f"%{q}%"),
                Member.cell_number.ilike(f"%{q}%"),
            )
        )
    if search_request.status:
        query = query.where(Member.status == search_request.status)
    if search_request.plan_option_id:
        query = query.where(Member.plan_option_id == search_request.plan_option_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    page = search_request.page
    page_size = search_request.page_size
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    members = result.scalars().all()

    return PaginatedMembersResponse(
        items=members,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )
