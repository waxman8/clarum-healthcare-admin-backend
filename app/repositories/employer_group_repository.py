# Auto-generated repository for EmployerGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.employers import EmployerGroup
from app.schemas.employer_group import EmployerGroupCreate, EmployerGroupUpdate


class EmployerGroupRepository:
    """Data-access layer for EmployerGroup entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[EmployerGroup]:
        query = select(EmployerGroup).where(EmployerGroup.is_deleted == False)
        if scheme_id is not None:
            query = query.where(EmployerGroup.scheme_id == scheme_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[EmployerGroup]:
        query = select(EmployerGroup).where(EmployerGroup.id == item_id).where(EmployerGroup.is_deleted == False)
        if scheme_id is not None:
            query = query.where(EmployerGroup.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: EmployerGroupCreate) -> EmployerGroup:
        obj = EmployerGroup(**payload.model_dump())
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: EmployerGroupUpdate, scheme_id: Optional[int] = None) -> Optional[EmployerGroup]:
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
