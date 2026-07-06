from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
import math
import json
from datetime import date, datetime, timedelta, timezone

from app.database import get_db
from app.models.billing import Dispute
from app.models.auth import User, AuditLog
from app.schemas.disputes import (
    DisputeCreate,
    DisputeResolve,
    DisputeResponse,
    PaginatedDisputesResponse,
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.constants import Role, DisputeStatus

router = APIRouter(prefix="/api/v1/disputes", tags=["disputes"])


def load_dispute_with_relations():
    return select(Dispute).options(
        selectinload(Dispute.member),
    )


def generate_dispute_number(scheme_code: str, sequence: int) -> str:
    now = datetime.now()
    return f"DIS-{scheme_code}-{now.strftime('%Y%m')}-{sequence:05d}"


@router.post("", response_model=DisputeResponse)
async def create_dispute(
    data: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scheme_id = _effective_scheme_id(current_user)
    if not scheme_id:
        raise HTTPException(status_code=400, detail="User is not scoped to a scheme")

    received = data.date_received or date.today()
    member_deadline = received + timedelta(days=90)
    admin_deadline = received + timedelta(days=30)

    # Sequence per scheme
    count_result = await db.execute(
        select(func.count(Dispute.id)).where(Dispute.scheme_id == scheme_id)
    )
    sequence = (count_result.scalar() or 0) + 1

    # Use scheme code if available, fallback to ID
    from app.models.auth import Scheme
    scheme_result = await db.execute(select(Scheme).where(Scheme.id == scheme_id))
    scheme = scheme_result.scalar_one_or_none()
    scheme_code = scheme.code if scheme else str(scheme_id)

    dispute_number = generate_dispute_number(scheme_code, sequence)

    dispute = Dispute(
        scheme_id=scheme_id,
        dispute_number=dispute_number,
        member_id=data.member_id,
        claim_id=data.claim_id,
        dispute_type=data.dispute_type,
        description=data.description,
        status=DisputeStatus.OPEN,
        date_received=received,
        member_deadline=member_deadline,
        admin_deadline=admin_deadline,
        created_by=current_user.id,
    )
    db.add(dispute)
    await db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="dispute",
        entity_id=dispute.id,
        action="create",
        new_value=json.dumps({"dispute_number": dispute_number, "member_id": data.member_id}),
    )
    db.add(audit)
    await db.commit()

    result = await db.execute(
        load_dispute_with_relations().where(Dispute.id == dispute.id)
    )
    return result.scalar_one()


@router.get("", response_model=PaginatedDisputesResponse)
async def list_disputes(
    status: Optional[str] = Query(None),
    is_overdue: Optional[bool] = Query(None, description="Filter disputes past admin deadline"),
    member_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = load_dispute_with_relations()

    _sid = _effective_scheme_id(current_user)
    if _sid is not None:
        query = query.where(Dispute.scheme_id == _sid)
    if status:
        query = query.where(Dispute.status == status)
    if is_overdue is True:
        query = query.where(
            Dispute.admin_deadline < date.today(),
            Dispute.status.in_(DisputeStatus.OPEN_STATUSES),
        )
    if member_id:
        query = query.where(Dispute.member_id == member_id)

    query = query.order_by(Dispute.admin_deadline.asc())

    base = select(Dispute)
    if _sid is not None:
        base = base.where(Dispute.scheme_id == _sid)
    if status:
        base = base.where(Dispute.status == status)
    if is_overdue is True:
        base = base.where(
            Dispute.admin_deadline < date.today(),
            Dispute.status.in_(DisputeStatus.OPEN_STATUSES),
        )
    if member_id:
        base = base.where(Dispute.member_id == member_id)
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedDisputesResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _sid = _effective_scheme_id(current_user)
    query = load_dispute_with_relations().where(Dispute.id == dispute_id)
    if _sid is not None:
        query = query.where(Dispute.scheme_id == _sid)
    result = await db.execute(query)
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


@router.patch("/{dispute_id}", response_model=DisputeResponse)
async def resolve_dispute(
    dispute_id: int,
    resolution: DisputeResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_RESOLVE_DISPUTE:
        raise HTTPException(status_code=403, detail="Not authorised to resolve disputes")

    _sid = _effective_scheme_id(current_user)
    query = load_dispute_with_relations().where(Dispute.id == dispute_id)
    if _sid is not None:
        query = query.where(Dispute.scheme_id == _sid)
    result = await db.execute(query)
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if dispute.status not in DisputeStatus.OPEN_STATUSES:
        raise HTTPException(status_code=400, detail="Dispute is already resolved")

    if resolution.status not in DisputeStatus.VALID_RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"status must be one of {DisputeStatus.VALID_RESOLUTIONS}")

    old_status = dispute.status
    dispute.status = resolution.status
    dispute.resolution = resolution.resolution
    dispute.resolved_by = current_user.id
    dispute.resolved_at = datetime.now(timezone.utc)
    dispute.updated_at = datetime.now(timezone.utc)

    if resolution.status == DisputeStatus.ESCALATED_TO_CMS:
        dispute.escalated_to_cms = True
        dispute.cms_reference = resolution.cms_reference
    else:
        dispute.escalated_to_cms = False

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="dispute",
        entity_id=dispute_id,
        action="resolve",
        old_value=json.dumps({"status": old_status}),
        new_value=json.dumps({"status": resolution.status, "resolution": resolution.resolution}),
    )
    db.add(audit)
    await db.commit()

    result = await db.execute(
        load_dispute_with_relations().where(Dispute.id == dispute_id)
    )
    return result.scalar_one()
