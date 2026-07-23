from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
import math
import json
from datetime import date, datetime, timezone

from app.database import get_db
from app.models.billing import ChronicRegistration
from app.models.auth import User, AuditLog
from app.schemas.chronic import (
    ChronicRegistrationCreate,
    ChronicRegistrationDecision,
    ChronicRegistrationResponse,
    PaginatedChronicResponse,
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.constants import Role, ChronicStatus, AuditAction

router = APIRouter(prefix="/api/v1/chronic-registrations", tags=["chronic"])


def load_registration_with_relations():
    return select(ChronicRegistration).options(
        selectinload(ChronicRegistration.member),
        selectinload(ChronicRegistration.icd10),
        selectinload(ChronicRegistration.dependant),
    )


@router.post("", response_model=ChronicRegistrationResponse)
async def create_chronic_registration(
    data: ChronicRegistrationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scheme_id = _effective_scheme_id(current_user)
    if not scheme_id:
        raise HTTPException(status_code=400, detail="User is not scoped to a scheme")

    reg = ChronicRegistration(
        scheme_id=scheme_id,
        member_id=data.member_id,
        dependant_id=data.dependant_id,
        icd10_code_id=data.icd10_code_id,
        status=ChronicStatus.PENDING,
        application_date=date.today(),
        notes=data.notes,
        is_pmb=True,
    )
    db.add(reg)
    await db.flush()

    audit = AuditLog(
        user_id=current_user.id,
        scheme_id=scheme_id,
        entity_type="chronic_registration",
        entity_id=reg.id,
        action=AuditAction.CREATE,
        new_value=json.dumps({"member_id": data.member_id, "icd10_code_id": data.icd10_code_id}),
    )
    db.add(audit)
    await db.commit()

    result = await db.execute(
        load_registration_with_relations().where(ChronicRegistration.id == reg.id)
    )
    return result.scalar_one()


@router.get("", response_model=PaginatedChronicResponse)
async def list_chronic_registrations(
    member_id: Optional[int] = Query(None),
    dependant_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _sid = _effective_scheme_id(current_user)
    query = load_registration_with_relations()

    if _sid is not None:
        query = query.where(ChronicRegistration.scheme_id == _sid)
    if member_id:
        query = query.where(ChronicRegistration.member_id == member_id)
    if dependant_id:
        query = query.where(ChronicRegistration.dependant_id == dependant_id)
    if status:
        query = query.where(ChronicRegistration.status == status)

    query = query.order_by(ChronicRegistration.created_at.desc())

    base = select(ChronicRegistration)
    if _sid is not None:
        base = base.where(ChronicRegistration.scheme_id == _sid)
    if member_id:
        base = base.where(ChronicRegistration.member_id == member_id)
    if dependant_id:
        base = base.where(ChronicRegistration.dependant_id == dependant_id)
    if status:
        base = base.where(ChronicRegistration.status == status)
    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedChronicResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{reg_id}", response_model=ChronicRegistrationResponse)
async def get_chronic_registration(
    reg_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _sid = _effective_scheme_id(current_user)
    query = load_registration_with_relations().where(ChronicRegistration.id == reg_id)
    if _sid is not None:
        query = query.where(ChronicRegistration.scheme_id == _sid)
    result = await db.execute(query)
    reg = result.scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Chronic registration not found")
    return reg


@router.patch("/{reg_id}", response_model=ChronicRegistrationResponse)
async def decide_chronic_registration(
    reg_id: int,
    decision: ChronicRegistrationDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_DECIDE_CHRONIC:
        raise HTTPException(status_code=403, detail="Not authorised to approve/decline chronic registrations")

    _sid = _effective_scheme_id(current_user)
    query = load_registration_with_relations().where(ChronicRegistration.id == reg_id)
    if _sid is not None:
        query = query.where(ChronicRegistration.scheme_id == _sid)
    result = await db.execute(query)
    reg = result.scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Chronic registration not found")

    if reg.status not in (ChronicStatus.PENDING, ChronicStatus.APPROVED):
        raise HTTPException(status_code=400, detail="Registration cannot be updated in its current status")

    if decision.status not in (ChronicStatus.APPROVED, ChronicStatus.DECLINED):
        raise HTTPException(status_code=400, detail="status must be APPROVED or DECLINED")

    old_status = reg.status
    reg.status = decision.status
    reg.decision_date = date.today()
    reg.decided_by = current_user.id
    if decision.notes:
        reg.notes = decision.notes
    if decision.approved_medicines is not None:
        reg.approved_medicines = json.dumps(decision.approved_medicines)
    reg.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        scheme_id=current_user.scheme_id,
        entity_type="chronic_registration",
        entity_id=reg_id,
        action=AuditAction.DECIDE,
        old_value=json.dumps({"status": old_status}),
        new_value=json.dumps({"status": decision.status}),
    )
    db.add(audit)
    await db.commit()

    result = await db.execute(
        load_registration_with_relations().where(ChronicRegistration.id == reg_id)
    )
    return result.scalar_one()
