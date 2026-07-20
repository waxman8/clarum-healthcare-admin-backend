from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import json
from datetime import datetime, timezone

from app.database import get_db
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.auth import User
from app.models.members import Member
from app.models.providers import Provider
from app.models.auth import Scheme
from app.schemas.authorisations import (
    AuthorisationCreate, AuthorisationApprove, AuthorisationDecline,
    AuthorisationResponse, PaginatedAuthorisationsResponse
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.constants import Role, AuthStatus, MemberStatus
from app.repositories import AuthorisationRepository
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/authorisations", tags=["authorisations"])


def generate_auth_number(scheme_code: str, sequence: int) -> str:
    year = datetime.now().year
    return f"{scheme_code}-{year}-{sequence:08d}"


@router.post("", response_model=AuthorisationResponse)
async def create_authorisation(
    auth_data: AuthorisationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AuthorisationRepository(db)

    # Validate member exists and belongs to the user's scheme
    member_res = await db.execute(select(Member).where(Member.id == auth_data.member_id))
    member = member_res.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail=f"Member {auth_data.member_id} not found")
    sid = _effective_scheme_id(current_user)
    if sid and member.scheme_id != sid:
        raise HTTPException(status_code=403, detail="Member does not belong to your scheme")
    if member.status != MemberStatus.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Member is not active (status: {member.status})")

    # Validate provider exists and is active
    provider_res = await db.execute(select(Provider).where(Provider.id == auth_data.requesting_provider_id))
    provider = provider_res.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider {auth_data.requesting_provider_id} not found")
    if not provider.is_active:
        raise HTTPException(status_code=400, detail="Provider is not active")

    # Get scheme code for auth number generation
    scheme_res = await db.execute(select(Scheme).where(Scheme.id == member.scheme_id))
    scheme = scheme_res.scalar_one()
    sequence = await repo.next_sequence()
    auth_number = generate_auth_number(scheme.code, sequence)

    auth = Authorisation(
        auth_number=auth_number,
        member_id=auth_data.member_id,
        dependant_id=auth_data.dependant_id,
        requesting_provider_id=auth_data.requesting_provider_id,
        icd10_codes=json.dumps(auth_data.icd10_codes),
        procedure_codes=json.dumps(auth_data.procedure_codes),
        auth_type=auth_data.auth_type,
        clinical_notes=auth_data.clinical_notes,
        created_by=current_user.id,
    )
    await repo.create(auth)

    for line_data in auth_data.lines:
        db.add(AuthorisationLine(
            auth_id=auth.id,
            tariff_code=line_data.tariff_code,
            description=line_data.description,
            quantity_requested=line_data.quantity_requested,
        ))

    log_audit(
        db, "authorisation", auth.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=member.scheme_id, entity_label=auth.auth_number,
        new_value=json.dumps({"auth_type": auth.auth_type}, default=str),
    )
    await repo.save()
    return await repo.get_by_id(auth.id)


@router.get("", response_model=PaginatedAuthorisationsResponse)
async def list_authorisations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    member_id: Optional[int] = None,
    dependant_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AuthorisationRepository(db)
    data = await repo.list(
        scheme_id=_effective_scheme_id(current_user),
        status=status,
        member_id=member_id,
        dependant_id=dependant_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedAuthorisationsResponse(**data)


@router.get("/{auth_id}", response_model=AuthorisationResponse)
async def get_authorisation(
    auth_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AuthorisationRepository(db)
    auth = await repo.get_by_id(auth_id)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorisation not found")
    return auth


@router.post("/{auth_id}/approve", response_model=AuthorisationResponse)
async def approve_authorisation(
    auth_id: int,
    approve_data: AuthorisationApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_APPROVE_AUTH:
        raise HTTPException(status_code=403, detail="Not authorised to approve authorisations")

    repo = AuthorisationRepository(db)
    auth = await repo.get_by_id(auth_id)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorisation not found")
    if auth.status != AuthStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only approve pending authorisations")

    auth.status = AuthStatus.APPROVED
    auth.approved_days = approve_data.approved_days
    if approve_data.clinical_notes:
        auth.clinical_notes = approve_data.clinical_notes
    auth.updated_at = datetime.now(timezone.utc)
    auth.modified_date = datetime.now(timezone.utc)
    auth.modified_user = current_user.id

    log_audit(
        db, "authorisation", auth.id, "approve",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=auth.member.scheme_id if auth.member else None, entity_label=auth.auth_number,
        new_value=json.dumps({"approved_days": approve_data.approved_days}, default=str),
    )

    if approve_data.approved_lines:
        for line_approval in approve_data.approved_lines:
            line_res = await db.execute(
                select(AuthorisationLine).where(
                    AuthorisationLine.id == line_approval.get("line_id"),
                    AuthorisationLine.auth_id == auth_id,
                )
            )
            line = line_res.scalar_one_or_none()
            if line:
                line.quantity_approved = line_approval.get("quantity_approved")
                line.reason_declined = line_approval.get("reason_declined")
    else:
        for line in auth.lines:
            line.quantity_approved = line.quantity_requested

    await repo.save()
    return await repo.get_by_id(auth_id)


@router.post("/{auth_id}/decline", response_model=AuthorisationResponse)
async def decline_authorisation(
    auth_id: int,
    decline_data: AuthorisationDecline,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_APPROVE_AUTH:
        raise HTTPException(status_code=403, detail="Not authorised to decline authorisations")

    repo = AuthorisationRepository(db)
    auth = await repo.get_by_id(auth_id)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorisation not found")
    if auth.status != AuthStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only decline pending authorisations")

    auth.status = AuthStatus.DECLINED
    auth.clinical_notes = decline_data.clinical_notes or f"Declined: {decline_data.reason}"
    auth.updated_at = datetime.now(timezone.utc)
    auth.modified_date = datetime.now(timezone.utc)
    auth.modified_user = current_user.id
    for line in auth.lines:
        line.quantity_approved = 0
        line.reason_declined = decline_data.reason

    log_audit(
        db, "authorisation", auth.id, "decline",
        user_id=current_user.id, user_role=current_user.role,
        scheme_id=auth.member.scheme_id if auth.member else None, entity_label=auth.auth_number,
        reason=decline_data.reason,
    )

    await repo.save()
    return await repo.get_by_id(auth_id)
