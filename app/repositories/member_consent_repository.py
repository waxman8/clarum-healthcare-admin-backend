from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.members import MemberConsent
from app.models.reference import ConsentPurpose


class MemberConsentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active_purposes(self) -> list[ConsentPurpose]:
        result = await self.db.execute(
            select(ConsentPurpose).where(ConsentPurpose.is_active == True).order_by(ConsentPurpose.code)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list_for_member(self, member_id: int, scheme_id: int) -> list[MemberConsent]:
        result = await self.db.execute(
            select(MemberConsent)
            .where(
                MemberConsent.member_id == member_id,
                MemberConsent.scheme_id == scheme_id,
            )
            .order_by(MemberConsent.purpose)
        )
        return list(result.scalars().all())

    async def get_for_member_purpose(
        self, member_id: int, scheme_id: int, purpose: str
    ) -> MemberConsent | None:
        result = await self.db.execute(
            select(MemberConsent).where(
                MemberConsent.member_id == member_id,
                MemberConsent.scheme_id == scheme_id,
                MemberConsent.purpose == purpose,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        member_id: int,
        scheme_id: int,
        purpose: str,
        consented: bool,
        granted_at,
        granted_by_user_id: int | None,
        withdrew_at=None,
        withdraw_reason: str | None = None,
    ) -> MemberConsent:
        consent = MemberConsent(
            member_id=member_id,
            scheme_id=scheme_id,
            purpose=purpose,
            consented=consented,
            granted_at=granted_at,
            granted_by_user_id=granted_by_user_id,
            withdrew_at=withdrew_at,
            withdraw_reason=withdraw_reason,
        )
        self.db.add(consent)
        await self.db.flush()
        return consent

    async def update(
        self,
        consent: MemberConsent,
        *,
        consented: bool,
        granted_at,
        granted_by_user_id: int | None,
        withdrew_at=None,
        withdraw_reason: str | None = None,
    ) -> MemberConsent:
        consent.consented = consented
        consent.granted_at = granted_at
        consent.granted_by_user_id = granted_by_user_id
        consent.withdrew_at = withdrew_at
        consent.withdraw_reason = withdraw_reason
        await self.db.flush()
        return consent
