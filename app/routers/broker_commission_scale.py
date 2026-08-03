# Auto-generated async CRUD router for BrokerCommissionScale
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id, require_roles
from app.constants import Role
from app.models.auth import User
from app.models.intermediaries import BrokerCommissionScale
from app.schemas.broker_commission_scale import BrokerCommissionScaleCreate, BrokerCommissionScaleUpdate, BrokerCommissionScaleRead, BrokerCommissionScaleAuditRead
from app.repositories.broker_commission_scale_repository import BrokerCommissionScaleRepository

router = APIRouter(prefix="/api/v1/broker-commission-scale", tags=["Broker Commission Scale"])


@router.get("", response_model=list[BrokerCommissionScaleRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    repo = BrokerCommissionScaleRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=BrokerCommissionScaleRead, status_code=201)
async def create_item(
    payload: BrokerCommissionScaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    from app.services.broker_commission_scale_service import BrokerCommissionScaleService
    repo = BrokerCommissionScaleRepository(db)
    service = BrokerCommissionScaleService(repo)
    scheme_id = _effective_scheme_id(current_user)
    return await service.create(payload, scheme_id, current_user.id)


@router.get("/{item_id}", response_model=BrokerCommissionScaleRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    repo = BrokerCommissionScaleRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.get("/{item_id}/audit", response_model=list[BrokerCommissionScaleAuditRead], status_code=200)
async def get_item_audit(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    from app.models.auth import AuditLog
    from sqlalchemy import select
    
    # First verify the user has access to this item
    repo = BrokerCommissionScaleRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")

    query = select(AuditLog).where(
        AuditLog.entity_type == "BrokerCommissionScale", 
        AuditLog.entity_id == item_id
    ).order_by(AuditLog.timestamp.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs

@router.patch("/{item_id}", response_model=BrokerCommissionScaleRead)
async def update_item(
    item_id: int,
    payload: BrokerCommissionScaleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    from app.services.broker_commission_scale_service import BrokerCommissionScaleService
    repo = BrokerCommissionScaleRepository(db)
    service = BrokerCommissionScaleService(repo)
    scheme_id = _effective_scheme_id(current_user)
    obj = await service.update(item_id, payload, scheme_id=scheme_id, user_id=current_user.id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_OFFICER)),
):
    from app.services.broker_commission_scale_service import BrokerCommissionScaleService
    repo = BrokerCommissionScaleRepository(db)
    service = BrokerCommissionScaleService(repo)
    scheme_id = _effective_scheme_id(current_user)
    deleted = await service.delete(item_id, scheme_id=scheme_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
