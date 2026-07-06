# Auto-generated async CRUD router for ManagedCareOrganisation
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.scheme_governance import ManagedCareOrganisation
from app.schemas.managed_care_organisation_mco import ManagedCareOrganisationCreate, ManagedCareOrganisationUpdate, ManagedCareOrganisationRead
from app.repositories.managed_care_organisation_mco_repository import ManagedCareOrganisationRepository

router = APIRouter(prefix="/api/v1/managed-care-organisation-mco", tags=["Managed Care Organisation (MCO)"])


@router.get("", response_model=list[ManagedCareOrganisationRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ManagedCareOrganisationRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=ManagedCareOrganisationRead, status_code=201)
async def create_item(
    payload: ManagedCareOrganisationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ManagedCareOrganisationRepository(db)
    return await repo.create(payload)


@router.get("/{item_id}", response_model=ManagedCareOrganisationRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ManagedCareOrganisationRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=ManagedCareOrganisationRead)
async def update_item(
    item_id: int,
    payload: ManagedCareOrganisationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ManagedCareOrganisationRepository(db)
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
    repo = ManagedCareOrganisationRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
