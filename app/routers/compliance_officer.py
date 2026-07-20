# Auto-generated async CRUD router for ComplianceOfficer
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.scheme_governance import ComplianceOfficer
from app.schemas.compliance_officer import ComplianceOfficerCreate, ComplianceOfficerUpdate, ComplianceOfficerRead
from app.repositories.compliance_officer_repository import ComplianceOfficerRepository
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/compliance-officer", tags=["Compliance Officer"])


@router.get("", response_model=list[ComplianceOfficerRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ComplianceOfficerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=ComplianceOfficerRead, status_code=201)
async def create_item(
    payload: ComplianceOfficerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ComplianceOfficerRepository(db)
    obj = await repo.create(payload)
    log_audit(
        db, "compliance_officer", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, scheme_id=_effective_scheme_id(current_user),
        entity_label=obj.full_name,
    )
    return obj


@router.get("/{item_id}", response_model=ComplianceOfficerRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ComplianceOfficerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=ComplianceOfficerRead)
async def update_item(
    item_id: int,
    payload: ComplianceOfficerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ComplianceOfficerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    changes = payload.model_dump(exclude_unset=True)
    obj = await repo.update(item_id, payload, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    if changes:
        log_audit(
            db, "compliance_officer", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, scheme_id=scheme_id,
            entity_label=obj.full_name, new_value=json.dumps(changes, default=str),
        )
    return obj


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ComplianceOfficerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    label = obj.full_name
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    log_audit(
        db, "compliance_officer", item_id, "delete",
        user_id=current_user.id, user_role=current_user.role, scheme_id=scheme_id, entity_label=label,
    )
