# Auto-generated repository for Brokerage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.intermediaries import Brokerage
from app.schemas.brokerage_fsp import BrokerageCreate, BrokerageUpdate


class BrokerageRepository:
    """Data-access layer for Brokerage entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[Brokerage]:
        query = select(Brokerage).where(Brokerage.is_deleted == False)
        if scheme_id is not None:
            query = query.where(Brokerage.scheme_id == scheme_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[Brokerage]:
        query = select(Brokerage).where(Brokerage.id == item_id).where(Brokerage.is_deleted == False)
        if scheme_id is not None:
            query = query.where(Brokerage.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: BrokerageCreate) -> Brokerage:
        obj = Brokerage(**payload.model_dump())
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: BrokerageUpdate, scheme_id: Optional[int] = None) -> Optional[Brokerage]:
        obj = await self.get(item_id, scheme_id)
        if obj is None:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        await self.db.flush()
        return obj

    async def soft_delete(self, item_id: int, scheme_id: Optional[int] = None, deleted_by: Optional[int] = None) -> bool:
        obj = await self.get(item_id, scheme_id)
        if obj is None:
            return False
        from datetime import datetime, timezone
        obj.is_deleted = True
        obj.deleted_at = datetime.now(timezone.utc)
        if deleted_by:
            obj.deleted_by = deleted_by
        await self.db.flush()
        return True
