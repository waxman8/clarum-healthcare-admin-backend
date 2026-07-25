from datetime import date, datetime, timedelta, timezone
import math
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.constants import DisputeStatus, Role
from app.database import get_db
from app.models.auth import User, AuditLog, Scheme
from app.models.billing import Dispute, DisputeComment, DisputeStatusHistory
from app.schemas.disputes import (
    DisputeCommentCreate,
    DisputeCommentListResponse,
    DisputeCommentResponse,
    DisputeCreate,
    DisputeListResponse,
    DisputeResponse,
    DisputeTransition,
)

router = APIRouter(prefix="/api/v1/disputes", tags=["disputes"])

_STATUS_MAP = {
    DisputeStatus.LEGACY_OPEN: DisputeStatus.NEW,
    DisputeStatus.LEGACY_UNDER_REVIEW: DisputeStatus.INVESTIGATING,
    DisputeStatus.LEGACY_UPHELD: DisputeStatus.RESOLVED,
    DisputeStatus.LEGACY_DISMISSED: DisputeStatus.REJECTED,
    DisputeStatus.LEGACY_ESCALATED_TO_CMS: DisputeStatus.REJECTED,
}
_ALLOWED_STATUSES = {
    DisputeStatus.NEW,
    DisputeStatus.INVESTIGATING,
    DisputeStatus.RESOLVED,
    DisputeStatus.REJECTED,
}
_ALLOWED_ROLES = set(Role.CAN_RESOLVE_DISPUTE)


def _normalize_status(value: str) -> str:
    upper = (value or "").upper()
    return _STATUS_MAP.get(upper, upper)


def _load_dispute_with_relations():
    return select(Dispute).options(selectinload(Dispute.member))


def _ensure_role_access(current_user: User):
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Not authorised to access disputes")


async def _get_scoped_dispute(db: AsyncSession, current_user: User, dispute_id: int) -> Dispute:
    _sid = _effective_scheme_id(current_user)
    query = _load_dispute_with_relations().where(Dispute.id == dispute_id)
    if _sid is not None:
        query = query.where(Dispute.scheme_id == _sid)
    result = await db.execute(query)
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


def _generate_dispute_number(scheme_code: str, sequence: int) -> str:
    now = datetime.now(timezone.utc)
    return f"DIS-{scheme_code}-{now.strftime('%Y%m')}-{sequence:05d}"


def _to_response(dispute: Dispute) -> DisputeResponse:
    return DisputeResponse(
        id=dispute.id,
        scheme_id=dispute.scheme_id,
        dispute_number=dispute.dispute_number,
        member_id=dispute.member_id,
        member=dispute.member,
        claim_id=dispute.claim_id,
        dispute_type=dispute.dispute_type,
        description=dispute.description,
        status=_normalize_status(dispute.status),
        status_changed_at=dispute.status_changed_at,
        sla_deadline=dispute.sla_deadline,
        date_received=dispute.date_received,
        member_deadline=dispute.member_deadline,
        admin_deadline=dispute.admin_deadline,
        resolution=dispute.resolution,
        escalated_to_cms=dispute.escalated_to_cms,
        cms_reference=dispute.cms_reference,
        resolved_at=dispute.resolved_at,
        created_at=dispute.created_at,
    )


def _to_utc_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _append_audit(
    *,
    user_id: int,
    dispute_id: int,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> AuditLog:
    return AuditLog(
        user_id=user_id,
        entity_type="dispute",
        entity_id=dispute_id,
        action=action,
        old_value=json.dumps(old_value) if old_value is not None else None,
        new_value=json.dumps(new_value) if new_value is not None else None,
    )


@router.post("", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def create_dispute(
    data: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    scheme_id = _effective_scheme_id(current_user)
    if not scheme_id:
        raise HTTPException(status_code=400, detail="User is not scoped to a scheme")

    received = data.date_received or date.today()
    member_deadline = received + timedelta(days=90)
    admin_deadline = received + timedelta(days=30)
    now = datetime.now(timezone.utc)

    count_result = await db.execute(select(func.count(Dispute.id)).where(Dispute.scheme_id == scheme_id))
    sequence = (count_result.scalar() or 0) + 1
    scheme_result = await db.execute(select(Scheme).where(Scheme.id == scheme_id))
    scheme = scheme_result.scalar_one_or_none()
    scheme_code = scheme.code if scheme else str(scheme_id)
    dispute_number = _generate_dispute_number(scheme_code, sequence)

    dispute = Dispute(
        scheme_id=scheme_id,
        dispute_number=dispute_number,
        member_id=data.member_id,
        claim_id=data.claim_id,
        dispute_type=data.dispute_type,
        description=data.description,
        status=DisputeStatus.NEW,
        status_changed_at=now,
        sla_deadline=_to_utc_datetime(admin_deadline),
        date_received=received,
        member_deadline=member_deadline,
        admin_deadline=admin_deadline,
        created_by=current_user.id,
    )
    db.add(dispute)
    await db.flush()

    db.add(
        DisputeStatusHistory(
            dispute_id=dispute.id,
            from_status=None,
            to_status=DisputeStatus.NEW,
            changed_by=current_user.id,
            changed_at=now,
        )
    )
    db.add(
        _append_audit(
            user_id=current_user.id,
            dispute_id=dispute.id,
            action="create",
            new_value={
                "status": DisputeStatus.NEW,
                "dispute_number": dispute.dispute_number,
                "member_id": dispute.member_id,
            },
        )
    )
    await db.commit()

    result = await db.execute(_load_dispute_with_relations().where(Dispute.id == dispute.id))
    return _to_response(result.scalar_one())


@router.get("", response_model=DisputeListResponse)
async def list_disputes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    query = _load_dispute_with_relations()
    _sid = _effective_scheme_id(current_user)
    if _sid is not None:
        query = query.where(Dispute.scheme_id == _sid)

    normalized_status = None
    if status:
        normalized_status = _normalize_status(status)
        if normalized_status not in _ALLOWED_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Use NEW, INVESTIGATING, RESOLVED, or REJECTED.",
            )
        matching = [k for k, v in _STATUS_MAP.items() if v == normalized_status]
        query = query.where(Dispute.status.in_([normalized_status, *matching]))

    query = query.order_by(Dispute.sla_deadline.asc().nulls_last(), Dispute.created_at.desc())

    base = select(Dispute)
    if _sid is not None:
        base = base.where(Dispute.scheme_id == _sid)
    if normalized_status:
        matching = [k for k, v in _STATUS_MAP.items() if v == normalized_status]
        base = base.where(Dispute.status.in_([normalized_status, *matching]))
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    return DisputeListResponse(items=[_to_response(item) for item in items], total=total)


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    dispute = await _get_scoped_dispute(db, current_user, dispute_id)
    return _to_response(dispute)


@router.post("/{dispute_id}/transition", response_model=DisputeResponse)
async def transition_dispute(
    dispute_id: int,
    body: DisputeTransition,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    dispute = await _get_scoped_dispute(db, current_user, dispute_id)

    from_status = _normalize_status(dispute.status)
    to_status = _normalize_status(body.to_status)
    if to_status not in _ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Invalid to_status. Use NEW, INVESTIGATING, RESOLVED, or REJECTED.",
        )

    legal = {
        DisputeStatus.NEW: {DisputeStatus.INVESTIGATING},
        DisputeStatus.INVESTIGATING: {DisputeStatus.RESOLVED, DisputeStatus.REJECTED},
        DisputeStatus.RESOLVED: set(),
        DisputeStatus.REJECTED: set(),
    }
    if to_status not in legal.get(from_status, set()):
        raise HTTPException(status_code=400, detail=f"Illegal transition from {from_status} to {to_status}")

    if to_status == DisputeStatus.RESOLVED and not body.resolution:
        raise HTTPException(status_code=400, detail="resolution is required when transitioning to RESOLVED")
    if to_status == DisputeStatus.REJECTED and not body.reason:
        raise HTTPException(status_code=400, detail="reason is required when transitioning to REJECTED")

    now = datetime.now(timezone.utc)
    dispute.status = to_status
    dispute.status_changed_at = now
    dispute.updated_at = now
    if to_status in DisputeStatus.TERMINAL_STATUSES:
        dispute.resolved_by = current_user.id
        dispute.resolved_at = now
    if body.resolution:
        dispute.resolution = body.resolution
    if body.reason:
        dispute.transition_reason = body.reason

    db.add(
        DisputeStatusHistory(
            dispute_id=dispute.id,
            from_status=from_status,
            to_status=to_status,
            reason=body.reason,
            resolution=body.resolution,
            changed_by=current_user.id,
            changed_at=now,
        )
    )
    db.add(
        _append_audit(
            user_id=current_user.id,
            dispute_id=dispute.id,
            action="transition",
            old_value={"status": from_status},
            new_value={"status": to_status, "resolution": body.resolution, "reason": body.reason},
        )
    )
    await db.commit()

    result = await db.execute(_load_dispute_with_relations().where(Dispute.id == dispute.id))
    return _to_response(result.scalar_one())


@router.get("/{dispute_id}/comments", response_model=DisputeCommentListResponse)
async def list_dispute_comments(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    await _get_scoped_dispute(db, current_user, dispute_id)
    result = await db.execute(
        select(DisputeComment)
        .options(selectinload(DisputeComment.created_by_user))
        .where(DisputeComment.dispute_id == dispute_id)
        .order_by(DisputeComment.created_at.asc())
    )
    items = []
    for c in result.scalars().all():
        author_name = c.created_by_user.full_name if c.created_by_user else None
        items.append(
            DisputeCommentResponse(
                id=c.id,
                comment=c.comment,
                created_at=c.created_at,
                author_name=author_name,
                created_by_name=author_name,
            )
        )
    return DisputeCommentListResponse(items=items)


@router.post("/{dispute_id}/comments", response_model=DisputeCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_dispute_comment(
    dispute_id: int,
    body: DisputeCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_role_access(current_user)
    await _get_scoped_dispute(db, current_user, dispute_id)
    now = datetime.now(timezone.utc)
    comment = DisputeComment(
        dispute_id=dispute_id,
        comment=body.comment,
        created_by=current_user.id,
        created_at=now,
    )
    db.add(comment)
    await db.flush()
    db.add(
        _append_audit(
            user_id=current_user.id,
            dispute_id=dispute_id,
            action="comment_add",
            new_value={"comment_id": comment.id},
        )
    )
    await db.commit()

    return DisputeCommentResponse(
        id=comment.id,
        comment=comment.comment,
        created_at=comment.created_at,
        author_name=current_user.full_name,
        created_by_name=current_user.full_name,
    )
