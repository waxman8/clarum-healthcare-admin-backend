from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claims import Claim
from app.models.recovery import RecoveryCase, RecoveryCaseClaimLink, RecoveryReceipt


class RecoveryCaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, scheme_id: int, recovery_type: Optional[str], status: Optional[str], page: int, page_size: int) -> dict:
        query = select(RecoveryCase).where(RecoveryCase.scheme_id == scheme_id)
        if recovery_type:
            query = query.where(RecoveryCase.recovery_type == recovery_type)
        if status:
            query = query.where(RecoveryCase.status == status)
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        result = await self.db.execute(query.order_by(RecoveryCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return {"items": list(result.scalars().all()), "total": total, "page": page, "page_size": page_size, "pages": math.ceil(total / page_size) if total else 1}

    async def get(self, case_id: int, scheme_id: int) -> Optional[RecoveryCase]:
        result = await self.db.execute(select(RecoveryCase).where(RecoveryCase.id == case_id, RecoveryCase.scheme_id == scheme_id))
        return result.scalar_one_or_none()

    async def get_links(self, case_id: int, scheme_id: int) -> list[RecoveryCaseClaimLink]:
        result = await self.db.execute(select(RecoveryCaseClaimLink).where(RecoveryCaseClaimLink.recovery_case_id == case_id, RecoveryCaseClaimLink.scheme_id == scheme_id))
        return list(result.scalars().all())

    async def get_receipts(self, case_id: int, scheme_id: int) -> list[RecoveryReceipt]:
        result = await self.db.execute(select(RecoveryReceipt).where(RecoveryReceipt.recovery_case_id == case_id, RecoveryReceipt.scheme_id == scheme_id).order_by(RecoveryReceipt.received_on.desc()))
        return list(result.scalars().all())

    async def get_claim(self, claim_id: int, scheme_id: int) -> Optional[Claim]:
        result = await self.db.execute(select(Claim).where(Claim.id == claim_id, Claim.scheme_id == scheme_id))
        return result.scalar_one_or_none()

    async def find_link(self, case_id: int, claim_id: int, scheme_id: int) -> Optional[RecoveryCaseClaimLink]:
        result = await self.db.execute(select(RecoveryCaseClaimLink).where(RecoveryCaseClaimLink.recovery_case_id == case_id, RecoveryCaseClaimLink.claim_id == claim_id, RecoveryCaseClaimLink.scheme_id == scheme_id))
        return result.scalar_one_or_none()

    async def add(self, item: object) -> None:
        self.db.add(item)
        await self.db.flush()
