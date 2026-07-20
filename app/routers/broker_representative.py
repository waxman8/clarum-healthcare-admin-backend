# Auto-generated async CRUD router for Broker
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.intermediaries import Broker
from app.schemas.broker_representative import BrokerCreate, BrokerUpdate, BrokerRead
from app.repositories.broker_representative_repository import BrokerRepository
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/broker-representative", tags=["Broker / Representative"])


@router.get("", response_model=list[BrokerRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=BrokerRead, status_code=201)
async def create_item(
    payload: BrokerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerRepository(db)
    obj = await repo.create(payload)
    log_audit(
        db, "broker", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, scheme_id=_effective_scheme_id(current_user),
        entity_label=obj.full_name,
    )
    return obj


@router.get("/{item_id}", response_model=BrokerRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=BrokerRead)
async def update_item(
    item_id: int,
    payload: BrokerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    changes = payload.model_dump(exclude_unset=True)
    obj = await repo.update(item_id, payload, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    if changes:
        log_audit(
            db, "broker", obj.id, "update",
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
    repo = BrokerRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    label = obj.full_name
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    log_audit(
        db, "broker", item_id, "delete",
        user_id=current_user.id, user_role=current_user.role, scheme_id=scheme_id, entity_label=label,
    )
