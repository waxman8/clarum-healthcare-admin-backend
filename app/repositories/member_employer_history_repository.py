# Repository for MemberEmployerHistory
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.employers import MemberEmployerHistory
from app.schemas.member_employer_history import MemberEmployerHistoryCreate, MemberEmployerHistoryUpdate


class MemberEmployerHistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[MemberEmployerHistory]:
        query = select(MemberEmployerHistory).where(MemberEmployerHistory.is_deleted == False)
        if scheme_id is not None:
            query = query.where(MemberEmployerHistory.scheme_id == scheme_id)
        query = query.order_by(MemberEmployerHistory.effective_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_member(self, member_id: int, scheme_id: Optional[int] = None) -> list[MemberEmployerHistory]:
        query = (
            select(MemberEmployerHistory)
            .where(MemberEmployerHistory.member_id == member_id)
            .where(MemberEmployerHistory.is_deleted == False)
        )
        if scheme_id is not None:
            query = query.where(MemberEmployerHistory.scheme_id == scheme_id)
        query = query.order_by(MemberEmployerHistory.effective_date.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_employer(self, employer_group_id: int, scheme_id: Optional[int] = None) -> list[MemberEmployerHistory]:
        query = (
            select(MemberEmployerHistory)
            .where(MemberEmployerHistory.employer_group_id == employer_group_id)
            .where(MemberEmployerHistory.is_deleted == False)
        )
        if scheme_id is not None:
            query = query.where(MemberEmployerHistory.scheme_id == scheme_id)
        query = query.order_by(MemberEmployerHistory.effective_date.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[MemberEmployerHistory]:
        query = select(MemberEmployerHistory).where(MemberEmployerHistory.id == item_id).where(MemberEmployerHistory.is_deleted == False)
        if scheme_id is not None:
            query = query.where(MemberEmployerHistory.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_current_for_member(self, member_id: int, scheme_id: Optional[int] = None) -> Optional[MemberEmployerHistory]:
        query = (
            select(MemberEmployerHistory)
            .where(MemberEmployerHistory.member_id == member_id)
            .where(MemberEmployerHistory.end_date == None)
            .where(MemberEmployerHistory.is_deleted == False)
        )
        if scheme_id is not None:
            query = query.where(MemberEmployerHistory.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: MemberEmployerHistoryCreate) -> MemberEmployerHistory:
        obj = MemberEmployerHistory(**payload.model_dump())
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: MemberEmployerHistoryUpdate, scheme_id: Optional[int] = None) -> Optional[MemberEmployerHistory]:
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
