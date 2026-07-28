# Auto-generated repository for MemberNominee
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.members import MemberNominee
from app.schemas.beneficiary_nomination import MemberNomineeCreate, MemberNomineeUpdate


class MemberNomineeRepository:
    """Data-access layer for MemberNominee entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> list[MemberNominee]:
        query = select(MemberNominee)
        if scheme_id is not None:
            query = query.where(MemberNominee.scheme_id == scheme_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, item_id: int, scheme_id: Optional[int] = None) -> Optional[MemberNominee]:
        query = select(MemberNominee).where(MemberNominee.id == item_id)
        if scheme_id is not None:
            query = query.where(MemberNominee.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: MemberNomineeCreate) -> MemberNominee:
        data = payload.model_dump()
        obj = MemberNominee(**data)
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def update(self, item_id: int, payload: MemberNomineeUpdate, scheme_id: Optional[int] = None) -> Optional[MemberNominee]:
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
