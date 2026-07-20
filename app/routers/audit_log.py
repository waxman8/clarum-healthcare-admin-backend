from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
import math

from app.database import get_db
from app.models.auth import AuditLog, User
from app.schemas.audit_log import AuditLogResponse, PaginatedAuditLogResponse
from app.auth.dependencies import get_current_user, _effective_scheme_id

router = APIRouter(prefix="/api/v1/audit-log", tags=["audit-log"])


@router.get("", response_model=PaginatedAuditLogResponse)
async def list_audit_log(
    entity_type: Optional[str] = Query(None, description="Comma-separated entity types, e.g. 'provider' or 'underwriting_decision,enrollment_questionnaire'"),
    search: Optional[str] = Query(None, description="Free-text search over item label, action, user, and old/new values"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id)

    if entity_type:
        types = [t.strip() for t in entity_type.split(",") if t.strip()]
        if types:
            base_query = base_query.where(AuditLog.entity_type.in_(types))

    if search:
        term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(
                AuditLog.entity_label.ilike(term),
                AuditLog.action.ilike(term),
                User.full_name.ilike(term),
                AuditLog.old_value.ilike(term),
                AuditLog.new_value.ilike(term),
                AuditLog.reason.ilike(term),
            )
        )

    sid = _effective_scheme_id(current_user)
    if sid is not None:
        base_query = base_query.where(or_(AuditLog.scheme_id == sid, AuditLog.scheme_id.is_(None)))

    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = base_query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    items = [
        AuditLogResponse(
            id=audit.id,
            entity_type=audit.entity_type,
            entity_id=audit.entity_id,
            entity_label=audit.entity_label,
            action=audit.action,
            old_value=audit.old_value,
            new_value=audit.new_value,
            timestamp=audit.timestamp,
            user_id=audit.user_id,
            user_name=user_full_name,
        )
        for audit, user_full_name in rows
    ]

    return PaginatedAuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )
