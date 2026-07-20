from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import CommunicationCategory, CommunicationChannel
from app.integrations.contracts import MessagingGateway
from app.integrations.registry import get
from app.models.auth import AuditLog
from app.models.members import Member
from app.repositories.member_communication_preference_repository import (
    MemberCommunicationPreferenceRepository,
)
from app.services.member_communication_preference_service import (
    MemberCommunicationPreferenceService,
)


@dataclass(frozen=True)
class CommunicationSendResult:
    outcome: str
    channel: str
    category: str
    provider_reference: str | None = None


class CommunicationsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemberCommunicationPreferenceRepository(db)
        self.pref_service = MemberCommunicationPreferenceService(db, self.repo)
        self.gateway: MessagingGateway = get(MessagingGateway)

    async def _get_member(self, member_id: int) -> Member:
        result = await self.db.execute(select(Member).where(Member.id == member_id))
        member = result.scalar_one_or_none()
        if member is None:
            raise ValueError("Member not found")
        return member

    async def _resolve_preference(self, member_id: int, channel: str, category: str):
        member = await self._get_member(member_id)
        self.pref_service.validate_channel(channel)
        self.pref_service.validate_category(category)
        prefs = await self.pref_service.ensure_defaults(member)
        pref_map = {(pref.channel, pref.category): pref for pref in prefs}
        return member, pref_map[(channel, category)]

    async def _log_suppression(self, member: Member, channel: str, category: str):
        self.db.add(
            AuditLog(
                user_id=None,
                user_role=None,
                entity_type="member_communication_preference",
                entity_id=member.id,
                action="suppressed_send",
                old_value=None,
                new_value=json.dumps({
                    "member_id": member.id,
                    "channel": channel,
                    "category": category,
                    "outcome": "SUPPRESSED",
                }),
            )
        )
        await self.db.flush()

    async def send_sms(self, member_id: int, category: str, body: str) -> CommunicationSendResult:
        member, pref = await self._resolve_preference(member_id, CommunicationChannel.SMS, category)
        if not pref.is_opted_in:
            await self._log_suppression(member, CommunicationChannel.SMS, category)
            return CommunicationSendResult(
                outcome="SUPPRESSED",
                channel=CommunicationChannel.SMS,
                category=category,
            )

        provider_reference = self.gateway.send_sms(member.cell_number or "", body)
        await self.db.flush()
        return CommunicationSendResult(
            outcome="SENT",
            channel=CommunicationChannel.SMS,
            category=category,
            provider_reference=provider_reference,
        )

    async def send_email(
        self,
        member_id: int,
        category: str,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> CommunicationSendResult:
        member, pref = await self._resolve_preference(member_id, CommunicationChannel.EMAIL, category)
        if not pref.is_opted_in:
            await self._log_suppression(member, CommunicationChannel.EMAIL, category)
            return CommunicationSendResult(
                outcome="SUPPRESSED",
                channel=CommunicationChannel.EMAIL,
                category=category,
            )

        provider_reference = self.gateway.send_email(to, subject, body_html, body_text)
        await self.db.flush()
        return CommunicationSendResult(
            outcome="SENT",
            channel=CommunicationChannel.EMAIL,
            category=category,
            provider_reference=provider_reference,
        )
