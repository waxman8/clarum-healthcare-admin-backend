from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import CommunicationCategory, CommunicationChannel, Role
from app.models.auth import AuditLog, User
from app.models.members import Member
from app.repositories.member_communication_preference_repository import (
    MemberCommunicationPreferenceRepository,
)
from app.schemas.members import (
    MemberCommunicationPreferenceUpdateItem,
)


class MemberCommunicationPreferenceService:
    def __init__(self, db: AsyncSession, repo: MemberCommunicationPreferenceRepository):
        self.db = db
        self.repo = repo

    @staticmethod
    def validate_channel(channel: str) -> str:
        if channel not in CommunicationChannel.ALL:
            raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        return channel

    @staticmethod
    def validate_category(category: str) -> str:
        if category not in CommunicationCategory.ALL:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        return category

    @staticmethod
    def can_edit(current_user: User) -> bool:
        return current_user.role in {Role.SUPER_ADMIN, Role.SCHEME_ADMIN}

    async def ensure_defaults(self, member: Member, actor_user_id: int | None = None):
        prefs = await self.repo.list_for_member(member.id, member.scheme_id)
        existing = {(pref.channel, pref.category) for pref in prefs}
        for category in CommunicationCategory.ALL:
            for channel in CommunicationChannel.ALL:
                key = (channel, category)
                if key in existing:
                    continue
                pref = await self.repo.create(
                    member_id=member.id,
                    scheme_id=member.scheme_id,
                    channel=channel,
                    category=category,
                    is_opted_in=True,
                    created_by=actor_user_id,
                )
                prefs.append(pref)
        return sorted(prefs, key=lambda pref: (pref.category, pref.channel))

    async def update_preferences(
        self,
        member: Member,
        payload: list[MemberCommunicationPreferenceUpdateItem],
        current_user: User,
    ):
        if not self.can_edit(current_user):
            raise HTTPException(status_code=403, detail="You are not allowed to edit communication preferences")

        prefs = await self.ensure_defaults(member, current_user.id)
        pref_map = {(pref.channel, pref.category): pref for pref in prefs}

        for item in payload:
            channel = self.validate_channel(item.channel)
            category = self.validate_category(item.category)
            pref = pref_map[(channel, category)]
            if pref.is_opted_in == item.is_opted_in:
                continue

            old_value = {
                "channel": pref.channel,
                "category": pref.category,
                "is_opted_in": pref.is_opted_in,
            }
            await self.repo.update(
                pref,
                is_opted_in=item.is_opted_in,
                updated_by=current_user.id,
            )
            new_value = {
                "channel": pref.channel,
                "category": pref.category,
                "is_opted_in": pref.is_opted_in,
            }
            self.db.add(
                AuditLog(
                    user_id=current_user.id,
                    scheme_id=member.scheme_id,
                    user_role=current_user.role,
                    entity_type="member_communication_preference",
                    entity_id=pref.id,
                    action="update",
                    old_value=json.dumps(old_value),
                    new_value=json.dumps(new_value),
                )
            )

        await self.db.flush()
        return await self.ensure_defaults(member, current_user.id)
