"""Claim repository — all Claim/ClaimLine queries in one place."""
import math
from datetime import date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.claims import Claim, ClaimLine


class ClaimRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Base query with eager-loaded relations
    # ------------------------------------------------------------------
    def _base_query(self):
        return select(Claim).options(
            selectinload(Claim.member),
            selectinload(Claim.provider),
            selectinload(Claim.lines),
            selectinload(Claim.dependant),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_by_id(self, claim_id: int, scheme_id: Optional[int] = None) -> Optional[Claim]:
        q = self._base_query().where(Claim.id == claim_id)
        if scheme_id is not None:
            q = q.where(Claim.scheme_id == scheme_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def list(
        self,
        scheme_id: Optional[int],
        status: Optional[str] = None,
        member_id: Optional[int] = None,
        dependant_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        q = self._base_query()

        if scheme_id is not None:
            q = q.where(Claim.scheme_id == scheme_id)
        if status:
            q = q.where(Claim.status == status)
        if member_id:
            q = q.where(Claim.member_id == member_id)
        if dependant_id:
            q = q.where(Claim.dependant_id == dependant_id)
        if provider_id:
            q = q.where(Claim.provider_id == provider_id)
        if date_from:
            q = q.where(Claim.date_of_service_from >= date_from)
        if date_to:
            q = q.where(Claim.date_of_service_to <= date_to)
        q = q.order_by(Claim.created_at.desc())

        # Count
        count_q = select(func.count(Claim.id))
        if scheme_id is not None:
            count_q = count_q.where(Claim.scheme_id == scheme_id)
        if status:
            count_q = count_q.where(Claim.status == status)
        if member_id:
            count_q = count_q.where(Claim.member_id == member_id)
        if dependant_id:
            count_q = count_q.where(Claim.dependant_id == dependant_id)
        total = (await self.db.execute(count_q)).scalar()

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

    async def count_by_status(self, scheme_id: int, *statuses: str) -> int:
        result = await self.db.execute(
            select(func.count(Claim.id)).where(
                Claim.scheme_id == scheme_id,
                Claim.status.in_(statuses),
            )
        )
        return result.scalar() or 0

    async def sum_approved(self, scheme_id: int, *statuses: str) -> int:
        result = await self.db.execute(
            select(func.sum(Claim.total_approved)).where(
                Claim.scheme_id == scheme_id,
                Claim.status.in_(statuses),
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Claim number generation
    # ------------------------------------------------------------------
    async def next_claim_number(self) -> str:
        from datetime import datetime
        now = datetime.now()
        count_res = await self.db.execute(select(func.count(Claim.id)))
        seq = (count_res.scalar() or 0) + 1
        return f"CLM-{now.strftime('%Y%m')}-{seq:06d}"

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def create(self, claim: Claim) -> Claim:
        self.db.add(claim)
        await self.db.flush()
        return claim

    async def save(self) -> None:
        await self.db.commit()
