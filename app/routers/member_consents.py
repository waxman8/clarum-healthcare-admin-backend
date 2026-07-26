from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import json
from datetime import datetime, timezone

from app.database import get_db
from app.models.auth import User
from app.models.members import Member, MemberConsent
from app.models.reference import ConsentPurpose
from app.schemas.member_consents import (
    ConsentPurposeResponse, MemberConsentResponse, CurrentConsentResponse,
    ConsentGrantRequest, ConsentWithdrawRequest,
)
from app.auth.dependencies import get_current_user, require_roles, _effective_scheme_id
from app.constants import Role, ConsentPurpose as ConsentPurposeConst
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1", tags=["consents"])


async def _get_member_scoped(member_id: int, db: AsyncSession, current_user: User) -> Member:
    sid = _effective_scheme_id(current_user)
    query = select(Member).where(Member.id == member_id)
    if sid is not None:
        query = query.where(Member.scheme_id == sid)
    result = await db.execute(query)
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.get("/consent-purposes", response_model=list[ConsentPurposeResponse])
async def list_consent_purposes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ConsentPurpose).where(ConsentPurpose.is_active == True).order_by(ConsentPurpose.id)
    )
    return result.scalars().all()


@router.get("/members/{member_id}/consents", response_model=list[CurrentConsentResponse])
async def get_member_consents(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current effective consent per purpose — the highest-version row for each purpose,
    or a 'not recorded' placeholder if the member has never had that purpose set."""
    await _get_member_scoped(member_id, db, current_user)

    purposes_result = await db.execute(
        select(ConsentPurpose).where(ConsentPurpose.is_active == True).order_by(ConsentPurpose.id)
    )
    purposes = purposes_result.scalars().all()

    consents_result = await db.execute(
        select(MemberConsent).where(MemberConsent.member_id == member_id)
    )
    latest_by_purpose: dict[str, MemberConsent] = {}
    for row in consents_result.scalars().all():
        current = latest_by_purpose.get(row.purpose)
        if current is None or row.version > current.version:
            latest_by_purpose[row.purpose] = row

    response = []
    for p in purposes:
        row = latest_by_purpose.get(p.code)
        if row is None:
            response.append(CurrentConsentResponse(purpose=p.code, description=p.description))
        else:
            response.append(CurrentConsentResponse(
                purpose=p.code,
                description=p.description,
                consented=row.consented,
                version=row.version,
                granted_at=row.granted_at,
                granted_by_user_id=row.granted_by_user_id,
                withdrew_at=row.withdrew_at,
                withdraw_reason=row.withdraw_reason,
            ))
    return response


@router.get("/members/{member_id}/consents/history", response_model=list[MemberConsentResponse])
async def get_member_consent_history(
    member_id: int,
    purpose: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_member_scoped(member_id, db, current_user)

    query = select(MemberConsent).where(MemberConsent.member_id == member_id)
    if purpose:
        query = query.where(MemberConsent.purpose == purpose)
    query = query.order_by(MemberConsent.purpose, MemberConsent.version.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def _next_version(db: AsyncSession, member_id: int, purpose: str) -> int:
    result = await db.execute(
        select(func.max(MemberConsent.version)).where(
            MemberConsent.member_id == member_id, MemberConsent.purpose == purpose
        )
    )
    return (result.scalar() or 0) + 1


@router.post("/members/{member_id}/consents/grant", response_model=MemberConsentResponse)
async def grant_consent(
    member_id: int,
    payload: ConsentGrantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*Role.CAN_RECORD_CONSENT)),
):
    if payload.purpose not in ConsentPurposeConst.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid purpose. Must be one of: {ConsentPurposeConst.ALL}")

    member = await _get_member_scoped(member_id, db, current_user)
    version = await _next_version(db, member_id, payload.purpose)
    now = datetime.now(timezone.utc)

    consent = MemberConsent(
        scheme_id=member.scheme_id,
        member_id=member_id,
        purpose=payload.purpose,
        consented=True,
        version=version,
        granted_at=now,
        granted_by_user_id=current_user.id,
    )
    db.add(consent)
    await db.flush()

    log_audit(
        db, "member_consent", consent.id, "grant",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=member.scheme_id, entity_label=f"{member.first_name} {member.surname} — {payload.purpose}",
        new_value=json.dumps({"purpose": payload.purpose, "consented": True, "version": version}),
    )
    await db.commit()
    await db.refresh(consent)
    return consent


@router.post("/members/{member_id}/consents/withdraw", response_model=MemberConsentResponse)
async def withdraw_consent(
    member_id: int,
    payload: ConsentWithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*Role.CAN_RECORD_CONSENT)),
):
    if payload.purpose not in ConsentPurposeConst.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid purpose. Must be one of: {ConsentPurposeConst.ALL}")
    if not payload.withdraw_reason or not payload.withdraw_reason.strip():
        raise HTTPException(status_code=400, detail="withdraw_reason is required")

    member = await _get_member_scoped(member_id, db, current_user)
    version = await _next_version(db, member_id, payload.purpose)
    now = datetime.now(timezone.utc)

    consent = MemberConsent(
        scheme_id=member.scheme_id,
        member_id=member_id,
        purpose=payload.purpose,
        consented=False,
        version=version,
        withdrew_at=now,
        withdraw_reason=payload.withdraw_reason,
        granted_by_user_id=current_user.id,
    )
    db.add(consent)
    await db.flush()

    log_audit(
        db, "member_consent", consent.id, "withdraw",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=member.scheme_id, entity_label=f"{member.first_name} {member.surname} — {payload.purpose}",
        new_value=json.dumps({"purpose": payload.purpose, "consented": False, "version": version}),
        reason=payload.withdraw_reason,
    )
    await db.commit()
    await db.refresh(consent)
    return consent
