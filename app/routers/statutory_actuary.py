# Auto-generated async CRUD router for StatutoryActuary
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.scheme_governance import StatutoryActuary
from app.schemas.statutory_actuary import StatutoryActuaryCreate, StatutoryActuaryUpdate, StatutoryActuaryRead
from app.repositories.statutory_actuary_repository import StatutoryActuaryRepository

router = APIRouter(prefix="/api/v1/statutory-actuary", tags=["Statutory Actuary"])


@router.get("", response_model=list[StatutoryActuaryRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = StatutoryActuaryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=StatutoryActuaryRead, status_code=201)
async def create_item(
    payload: StatutoryActuaryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = StatutoryActuaryRepository(db)
    return await repo.create(payload)


@router.get("/{item_id}", response_model=StatutoryActuaryRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = StatutoryActuaryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=StatutoryActuaryRead)
async def update_item(
    item_id: int,
    payload: StatutoryActuaryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = StatutoryActuaryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.update(item_id, payload, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = StatutoryActuaryRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
