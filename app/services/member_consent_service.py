from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Role
from app.models.auth import AuditLog, User
from app.models.members import Member, MemberConsent
from app.repositories.member_consent_repository import MemberConsentRepository
from app.schemas.members import (
    ConsentAuditLogEntryRead,
    ConsentPurposeRead,
    MemberConsentMatrixItem,
    MemberConsentRead,
)


def _consent_payload(consent: MemberConsent) -> dict:
    return {
        "purpose": consent.purpose,
        "consented": consent.consented,
        "granted_at": consent.granted_at.isoformat() if consent.granted_at else None,
        "withdrew_at": consent.withdrew_at.isoformat() if consent.withdrew_at else None,
        "withdraw_reason": consent.withdraw_reason,
    }


class MemberConsentService:
    def __init__(self, db: AsyncSession, repo: MemberConsentRepository):
        self.db = db
        self.repo = repo

    @staticmethod
    def can_record(current_user: User) -> bool:
        return current_user.role in Role.CAN_RECORD_CONSENT

    async def validate_purpose(self, purpose: str) -> str:
        purposes = await self.repo.list_active_purposes()
        if purpose not in {p.code for p in purposes}:
            raise HTTPException(status_code=400, detail=f"Invalid consent purpose: {purpose}")
        return purpose

    async def get_matrix(self, member: Member) -> list[MemberConsentMatrixItem]:
        purposes = await self.repo.list_active_purposes()
        rows = await self.repo.list_for_member(member.id, member.scheme_id)
        by_purpose = {row.purpose: row for row in rows}

        return [
            MemberConsentMatrixItem(
                purpose=ConsentPurposeRead.model_validate(purpose),
                current=MemberConsentRead.model_validate(by_purpose[purpose.code])
                if purpose.code in by_purpose
                else None,
            )
            for purpose in purposes
        ]

    async def record_consent(
        self,
        member: Member,
        purpose: str,
        consented: bool,
        reason: str | None,
        current_user: User,
    ) -> list[MemberConsentMatrixItem]:
        if not self.can_record(current_user):
            raise HTTPException(status_code=403, detail="You are not allowed to record consent")

        await self.validate_purpose(purpose)

        if not consented and not reason:
            raise HTTPException(status_code=400, detail="A reason is required to withdraw consent")

        existing = await self.repo.get_for_member_purpose(member.id, member.scheme_id, purpose)
        old_value = _consent_payload(existing) if existing else None

        now = datetime.now(timezone.utc)
        if existing:
            consent = await self.repo.update(
                existing,
                consented=consented,
                granted_at=now,
                granted_by_user_id=current_user.id,
                withdrew_at=now if not consented else None,
                withdraw_reason=reason if not consented else None,
            )
        else:
            consent = await self.repo.create(
                member_id=member.id,
                scheme_id=member.scheme_id,
                purpose=purpose,
                consented=consented,
                granted_at=now,
                granted_by_user_id=current_user.id,
                withdrew_at=now if not consented else None,
                withdraw_reason=reason if not consented else None,
            )

        self.db.add(
            AuditLog(
                user_id=current_user.id,
                user_role=current_user.role,
                entity_type="member_consent",
                entity_id=consent.id,
                action="grant" if consented else "withdraw",
                old_value=json.dumps(old_value) if old_value else None,
                new_value=json.dumps(_consent_payload(consent)),
                reason=reason,
            )
        )

        await self.db.flush()
        return await self.get_matrix(member)

    async def get_audit_log(self, member: Member) -> list[ConsentAuditLogEntryRead]:
        rows = await self.repo.list_for_member(member.id, member.scheme_id)
        entity_ids = [row.id for row in rows]
        if not entity_ids:
            return []

        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "member_consent", AuditLog.entity_id.in_(entity_ids))
            .order_by(AuditLog.timestamp.desc())
        )
        logs = result.scalars().all()
        return [ConsentAuditLogEntryRead.model_validate(log) for log in logs]
