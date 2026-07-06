"""Member repository — all Member/Dependant queries in one place."""
import math
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.members import Member, Dependant
from app.models.auth import Scheme


class MemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Base query
    # ------------------------------------------------------------------
    def _base_query(self, scheme_id: Optional[int] = None):
        q = select(Member).options(
            selectinload(Member.dependants),
            selectinload(Member.plan_option),
        )
        if scheme_id is not None:
            q = q.where(Member.scheme_id == scheme_id)
        return q

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_by_id(self, member_id: int, scheme_id: Optional[int] = None) -> Optional[Member]:
        q = self._base_query(scheme_id).where(Member.id == member_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def get_by_membership_number(
        self, membership_number: str, scheme_id: Optional[int] = None
    ) -> Optional[Member]:
        q = self._base_query(scheme_id).where(Member.membership_number == membership_number)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def list(
        self,
        scheme_id: Optional[int],
        search: Optional[str] = None,
        status: Optional[str] = None,
        plan_option_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        q = self._base_query(scheme_id)

        if search:
            q = q.where(
                or_(
                    Member.first_name.ilike(f"%{search}%"),
                    Member.surname.ilike(f"%{search}%"),
                    Member.membership_number.ilike(f"%{search}%"),
                    Member.id_number.ilike(f"%{search}%"),
                )
            )
        if status:
            q = q.where(Member.status == status)
        if plan_option_id:
            q = q.where(Member.plan_option_id == plan_option_id)

        q = q.order_by(Member.surname, Member.first_name)

        # Count
        count_base = select(func.count(Member.id))
        if scheme_id is not None:
            count_base = count_base.where(Member.scheme_id == scheme_id)
        if search:
            count_base = count_base.where(
                or_(
                    Member.first_name.ilike(f"%{search}%"),
                    Member.surname.ilike(f"%{search}%"),
                    Member.membership_number.ilike(f"%{search}%"),
                    Member.id_number.ilike(f"%{search}%"),
                )
            )
        if status:
            count_base = count_base.where(Member.status == status)
        if plan_option_id:
            count_base = count_base.where(Member.plan_option_id == plan_option_id)
        total = (await self.db.execute(count_base)).scalar()

        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size) if total > 0 else 1,
        }

    async def count_active(self, scheme_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Member.id)).where(
                Member.scheme_id == scheme_id,
                Member.status == "active",
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Membership number generation
    # ------------------------------------------------------------------
    async def next_membership_number(self, scheme_id: int) -> str:
        from datetime import date
        scheme_res = await self.db.execute(select(Scheme).where(Scheme.id == scheme_id))
        scheme = scheme_res.scalar_one()
        year = date.today().year
        count_res = await self.db.execute(
            select(func.count(Member.id)).where(Member.scheme_id == scheme_id)
        )
        seq = (count_res.scalar() or 0) + 1
        return f"{scheme.code}-{year}-{seq:06d}"

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def create(self, member: Member) -> Member:
        self.db.add(member)
        await self.db.flush()
        return member

    async def save(self) -> None:
        await self.db.commit()
