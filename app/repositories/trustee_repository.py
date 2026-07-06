# Auto-generated repository for Trustee
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.scheme_governance import Trustee
from app.schemas.trustee import TrusteeCreate, TrusteeUpdate


class TrusteeRepository:
    """Data-access layer for Trustee entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[Trustee]:
        query = select(Trustee).where(Trustee.is_deleted == False)
        if scheme_id is not None:
            query = query.where(Trustee.scheme_id == scheme_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[Trustee]:
        query = select(Trustee).where(Trustee.id == item_id).where(Trustee.is_deleted == False)
        if scheme_id is not None:
            query = query.where(Trustee.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: TrusteeCreate) -> Trustee:
        obj = Trustee(**payload.model_dump())
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: TrusteeUpdate, scheme_id: Optional[int] = None) -> Optional[Trustee]:
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
