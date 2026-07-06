# Router for MemberEmployerHistory
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.employers import EmployerGroup
from app.schemas.member_employer_history import (
    MemberEmployerHistoryCreate, MemberEmployerHistoryUpdate, MemberEmployerHistoryRead,
)
from app.repositories.member_employer_history_repository import MemberEmployerHistoryRepository
from app.repositories.employer_group_repository import EmployerGroupRepository

router = APIRouter(prefix="/api/v1/member-employer-history", tags=["Member Employer History"])


async def _enrich_with_employer_name(items, db, scheme_id):
    """Attach employer_name from employer_groups for display."""
    if not items:
        return []
    employer_ids = {i.employer_group_id for i in items}
    repo = EmployerGroupRepository(db)
    employer_map = {}
    for eid in employer_ids:
        eg = await repo.get(eid, scheme_id=scheme_id)
        if eg:
            employer_map[eid] = eg.company_name
    result = []
    for item in items:
        data = MemberEmployerHistoryRead.model_validate(item)
        data.employer_name = employer_map.get(item.employer_group_id)
        result.append(data)
    return result


@router.get("", response_model=list[MemberEmployerHistoryRead])
async def list_items(
    member_id: Optional[int] = Query(None),
    employer_group_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = MemberEmployerHistoryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    if member_id:
        items = await repo.list_by_member(member_id, scheme_id=scheme_id)
    elif employer_group_id:
        items = await repo.list_by_employer(employer_group_id, scheme_id=scheme_id)
    else:
        items = await repo.list(scheme_id=scheme_id)
    return await _enrich_with_employer_name(items, db, scheme_id)


@router.post("", response_model=MemberEmployerHistoryRead, status_code=201)
async def create_item(
    payload: MemberEmployerHistoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = MemberEmployerHistoryRepository(db)
    scheme_id = _effective_scheme_id(current_user)

    # Close any existing current employer record for this member
    current = await repo.get_current_for_member(payload.member_id, scheme_id=scheme_id)
    if current:
        from app.schemas.member_employer_history import MemberEmployerHistoryUpdate
        from datetime import timedelta
        end_date = payload.effective_date - timedelta(days=1)
        await repo.update(current.id, MemberEmployerHistoryUpdate(
            end_date=end_date,
            employment_status=current.employment_status if current.employment_status != "ACTIVE" else "RESIGNED",
        ), scheme_id=scheme_id)

    obj = await repo.create(payload)
    enriched = await _enrich_with_employer_name([obj], db, scheme_id)
    return enriched[0]


@router.get("/{item_id}", response_model=MemberEmployerHistoryRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = MemberEmployerHistoryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    enriched = await _enrich_with_employer_name([obj], db, scheme_id)
    return enriched[0]


@router.patch("/{item_id}", response_model=MemberEmployerHistoryRead)
async def update_item(
    item_id: int,
    payload: MemberEmployerHistoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = MemberEmployerHistoryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.update(item_id, payload, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    enriched = await _enrich_with_employer_name([obj], db, scheme_id)
    return enriched[0]


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = MemberEmployerHistoryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
