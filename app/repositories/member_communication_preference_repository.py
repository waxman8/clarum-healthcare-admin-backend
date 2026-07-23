from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.members import MemberCommunicationPreference


class MemberCommunicationPreferenceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_member(self, member_id: int, scheme_id: int) -> list[MemberCommunicationPreference]:
        result = await self.db.execute(
            select(MemberCommunicationPreference)
            .where(
                MemberCommunicationPreference.member_id == member_id,
                MemberCommunicationPreference.scheme_id == scheme_id,
            )
            .order_by(MemberCommunicationPreference.category, MemberCommunicationPreference.channel)
        )
        return list(result.scalars().all())

    async def get_by_member_channel_category(
        self,
        member_id: int,
        scheme_id: int,
        channel: str,
        category: str,
    ) -> MemberCommunicationPreference | None:
        result = await self.db.execute(
            select(MemberCommunicationPreference).where(
                MemberCommunicationPreference.member_id == member_id,
                MemberCommunicationPreference.scheme_id == scheme_id,
                MemberCommunicationPreference.channel == channel,
                MemberCommunicationPreference.category == category,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        member_id: int,
        scheme_id: int,
        channel: str,
        category: str,
        is_opted_in: bool,
        created_by: int | None,
    ) -> MemberCommunicationPreference:
        pref = MemberCommunicationPreference(
            member_id=member_id,
            scheme_id=scheme_id,
            channel=channel,
            category=category,
            is_opted_in=is_opted_in,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(pref)
        await self.db.flush()
        return pref

    async def update(
        self,
        pref: MemberCommunicationPreference,
        *,
        is_opted_in: bool,
        updated_by: int | None,
    ) -> MemberCommunicationPreference:
        pref.is_opted_in = is_opted_in
        pref.updated_by = updated_by
        await self.db.flush()
        return pref
