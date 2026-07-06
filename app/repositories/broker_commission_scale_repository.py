# Auto-generated repository for BrokerCommissionScale
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.intermediaries import BrokerCommissionScale
from app.schemas.broker_commission_scale import BrokerCommissionScaleCreate, BrokerCommissionScaleUpdate


class BrokerCommissionScaleRepository:
    """Data-access layer for BrokerCommissionScale entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[BrokerCommissionScale]:
        query = select(BrokerCommissionScale)
        if scheme_id is not None:
            query = query.where(BrokerCommissionScale.scheme_id == scheme_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[BrokerCommissionScale]:
        query = select(BrokerCommissionScale).where(BrokerCommissionScale.id == item_id)
        if scheme_id is not None:
            query = query.where(BrokerCommissionScale.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: BrokerCommissionScaleCreate) -> BrokerCommissionScale:
        obj = BrokerCommissionScale(**payload.model_dump())
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: BrokerCommissionScaleUpdate, scheme_id: Optional[int] = None) -> Optional[BrokerCommissionScale]:
        obj = await self.get(item_id, scheme_id)
        if obj is None:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        await self.db.flush()
        return obj

    async def delete(self, item_id: int, scheme_id: Optional[int] = None) -> bool:
        obj = await self.get(item_id, scheme_id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True
