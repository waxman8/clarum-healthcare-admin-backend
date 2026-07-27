from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import func, or_, select
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
        result = await self.db.execute(
            select(RecoveryCaseClaimLink, Claim.claim_number)
            .outerjoin(Claim, Claim.id == RecoveryCaseClaimLink.claim_id)
            .where(RecoveryCaseClaimLink.recovery_case_id == case_id, RecoveryCaseClaimLink.scheme_id == scheme_id)
        )
        links = []
        for link, claim_number in result.all():
            link.claim_number = claim_number
            links.append(link)
        return links

    async def get_receipts(self, case_id: int, scheme_id: int) -> list[RecoveryReceipt]:
        result = await self.db.execute(select(RecoveryReceipt).where(RecoveryReceipt.recovery_case_id == case_id, RecoveryReceipt.scheme_id == scheme_id).order_by(RecoveryReceipt.received_on.desc()))
        return list(result.scalars().all())

    async def get_claim(self, claim_identifier: int | str, scheme_id: int) -> Optional[Claim]:
        identifier_str = str(claim_identifier).strip()
        if identifier_str.isdigit():
            query = select(Claim).where(
                or_(Claim.id == int(identifier_str), Claim.claim_number == identifier_str),
                Claim.scheme_id == scheme_id,
            )
        else:
            query = select(Claim).where(Claim.claim_number == identifier_str, Claim.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def find_link(self, case_id: int, claim_id: int, scheme_id: int) -> Optional[RecoveryCaseClaimLink]:
        result = await self.db.execute(select(RecoveryCaseClaimLink).where(RecoveryCaseClaimLink.recovery_case_id == case_id, RecoveryCaseClaimLink.claim_id == claim_id, RecoveryCaseClaimLink.scheme_id == scheme_id))
        return result.scalar_one_or_none()

    async def add(self, item: object) -> None:
        self.db.add(item)
        await self.db.flush()
