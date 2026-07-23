from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user, check_permissions
from app.models.auth import User
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.repositories.audit_log_repository import AuditLogRepository
from app.constants import Role
from typing import Optional
from datetime import datetime

router = APIRouter(
    prefix="/api/v1/audit-log",
    tags=["Audit Log"],
    dependencies=[Depends(get_current_user), Depends(check_permissions(Role.CAN_VIEW_AUDIT_LOG))]
)


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    actor_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = AuditLogRepository(db)
    items, total = await repo.list(
        scheme_id=current_user.scheme_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size
    )
    
    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{audit_log_id}", response_model=AuditLogResponse)
async def get_audit_log_detail(
    audit_log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = AuditLogRepository(db)
    item = await repo.get(scheme_id=current_user.scheme_id, audit_log_id=audit_log_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found or access denied"
        )
        
    return item


# Mutation endpoints explicitly return 405 Method Not Allowed as per spec
@router.post("", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
@router.post("/", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def create_audit_log():
    raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)


@router.put("/{audit_log_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
@router.patch("/{audit_log_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def update_audit_log(audit_log_id: int):
    raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)


@router.delete("/{audit_log_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def delete_audit_log(audit_log_id: int):
    raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
