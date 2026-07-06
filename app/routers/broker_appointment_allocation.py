# Auto-generated async CRUD router for BrokerAppointment
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.models.intermediaries import BrokerAppointment
from app.schemas.broker_appointment_allocation import BrokerAppointmentCreate, BrokerAppointmentUpdate, BrokerAppointmentRead
from app.repositories.broker_appointment_allocation_repository import BrokerAppointmentRepository

router = APIRouter(prefix="/api/v1/broker-appointment-allocation", tags=["Broker Appointment / Allocation"])


@router.get("", response_model=list[BrokerAppointmentRead])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerAppointmentRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    return await repo.list(scheme_id=scheme_id)


@router.post("", response_model=BrokerAppointmentRead, status_code=201)
async def create_item(
    payload: BrokerAppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerAppointmentRepository(db)
    return await repo.create(payload)


@router.get("/{item_id}", response_model=BrokerAppointmentRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerAppointmentRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    obj = await repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=BrokerAppointmentRead)
async def update_item(
    item_id: int,
    payload: BrokerAppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = BrokerAppointmentRepository(db)
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
    repo = BrokerAppointmentRepository(db)
    scheme_id = _effective_scheme_id(current_user)
    deleted = await repo.soft_delete(item_id, scheme_id=scheme_id, deleted_by=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
