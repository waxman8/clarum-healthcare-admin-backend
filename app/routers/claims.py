from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Optional
import math
import json
from datetime import datetime, timezone, date

from app.database import get_db, engine
from app.models.claims import Claim, ClaimLine
from app.models.billing import ClaimAdjudicationLog
from app.models.reference import TariffCode, ICD10Code
from app.models.auth import User, AuditLog
from app.schemas.claims import (
    ClaimCreate, ClaimAdjudicate, ClaimOverride,
    ClaimResponse, PaginatedClaimsResponse, RulesEngineResult, AuditTrailEntry
)
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.services.rules_engine import run_rules_engine, run_full_adjudication
from app.constants import Role, ClaimStatus
from app.repositories import ClaimRepository

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


def generate_claim_number(sequence: int) -> str:
    now = datetime.now()
    return f"CLM-{now.strftime('%Y%m')}-{sequence:06d}"


def load_claim_with_relations(db: AsyncSession):
    return select(Claim).options(
        selectinload(Claim.member),
        selectinload(Claim.provider),
        selectinload(Claim.lines),
        selectinload(Claim.dependant),
    )


@router.post("", response_model=ClaimResponse)
async def create_claim(
    claim_data: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count_result = await db.execute(select(func.count(Claim.id)))
    count = count_result.scalar() + 1
    claim_number = generate_claim_number(count)

    total_billed = sum(line.billed_amount for line in claim_data.lines)

    # Check for PMB
    is_pmb = False
    for line in claim_data.lines:
        if line.icd10_code:
            icd_result = await db.execute(
                select(ICD10Code).where(ICD10Code.code == line.icd10_code, ICD10Code.is_pmb == True)
            )
            if icd_result.scalar_one_or_none():
                is_pmb = True
                break

    claim = Claim(
        claim_number=claim_number,
        scheme_id=claim_data.scheme_id,
        member_id=claim_data.member_id,
        dependant_id=claim_data.dependant_id,
        provider_id=claim_data.provider_id,
        auth_number=claim_data.auth_number,
        date_of_service_from=claim_data.date_of_service_from,
        date_of_service_to=claim_data.date_of_service_to,
        date_received=date.today(),
        claim_type=claim_data.claim_type,
        status=ClaimStatus.RECEIVED,
        total_billed=total_billed,
        is_pmb=is_pmb,
    )
    db.add(claim)
    await db.flush()

    for line_data in claim_data.lines:
        # Get NHRPL rate
        nhrpl_rate = None
        tariff_result = await db.execute(
            select(TariffCode).where(TariffCode.code == line_data.tariff_code)
        )
        tariff = tariff_result.scalar_one_or_none()
        if tariff:
            nhrpl_rate = tariff.nhrpl_rate

        # Check if PMB line
        is_pmb_line = False
        if line_data.icd10_code:
            icd_result = await db.execute(
                select(ICD10Code).where(ICD10Code.code == line_data.icd10_code, ICD10Code.is_pmb == True)
            )
            is_pmb_line = icd_result.scalar_one_or_none() is not None

        line = ClaimLine(
            claim_id=claim.id,
            tariff_code=line_data.tariff_code,
            description=line_data.description,
            icd10_code=line_data.icd10_code,
            quantity=line_data.quantity,
            billed_amount=line_data.billed_amount,
            nhrpl_rate=nhrpl_rate,
            is_pmb_line=is_pmb_line,
        )
        db.add(line)

    await db.commit()

    result = await db.execute(load_claim_with_relations(db).where(Claim.id == claim.id))
    return result.scalar_one()


@router.get("", response_model=PaginatedClaimsResponse)
async def list_claims(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    member_id: Optional[int] = None,
    dependant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = load_claim_with_relations(db)

    _sid = _effective_scheme_id(current_user)
    if _sid is not None:
        query = query.where(Claim.scheme_id == _sid)
    if status:
        query = query.where(Claim.status == status)
    if member_id:
        query = query.where(Claim.member_id == member_id)
    if dependant_id:
        query = query.where(Claim.dependant_id == dependant_id)
    if provider_id:
        query = query.where(Claim.provider_id == provider_id)
    if date_from:
        query = query.where(Claim.date_of_service_from >= date_from)
    if date_to:
        query = query.where(Claim.date_of_service_to <= date_to)

    query = query.order_by(Claim.created_at.desc())

    base_count = select(Claim)
    if _sid is not None:
        base_count = base_count.where(Claim.scheme_id == _sid)
    if status:
        base_count = base_count.where(Claim.status == status)
    if member_id:
        base_count = base_count.where(Claim.member_id == member_id)
    if dependant_id:
        base_count = base_count.where(Claim.dependant_id == dependant_id)
    count_query = select(func.count()).select_from(base_count.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    claims = result.scalars().all()

    return PaginatedClaimsResponse(
        items=claims,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _sid = _effective_scheme_id(current_user)
    query = load_claim_with_relations(db).where(Claim.id == claim_id)
    if _sid is not None:
        query = query.where(Claim.scheme_id == _sid)
    result = await db.execute(query)
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


async def _run_adjudication_background(claim_id: int, user_id: int) -> None:
    """
    Background task: runs the full 7-stage adjudication pipeline in its own
    DB session so the HTTP response is not blocked. Status transitions:
      received → in_adjudication (set immediately on the request thread)
      in_adjudication → approved | rejected | partial (set here)
    """
    AsyncSession_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSession_() as db:
        result = await db.execute(load_claim_with_relations(db).where(Claim.id == claim_id))
        claim = result.scalar_one_or_none()
        if not claim:
            return

        await run_full_adjudication(db=db, claim=claim, persist_logs=True)

        await db.refresh(claim)
        total_approved = sum(line.approved_amount or 0 for line in claim.lines)
        total_member_liability = sum(line.member_liability or 0 for line in claim.lines)
        any_rejected = any((line.approved_amount or 0) == 0 for line in claim.lines)
        all_approved = all((line.approved_amount or 0) > 0 for line in claim.lines)

        claim.total_approved = total_approved
        claim.total_member_liability = total_member_liability
        claim.total_scheme_liability = total_approved

        if all_approved:
            claim.status = ClaimStatus.APPROVED
        elif any_rejected and total_approved == 0:
            claim.status = ClaimStatus.REJECTED
        else:
            claim.status = ClaimStatus.PARTIAL

        claim.adjudicated_by = user_id
        claim.adjudicated_at = datetime.now(timezone.utc)
        claim.updated_at = datetime.now(timezone.utc)

        db.add(AuditLog(
            user_id=user_id,
            entity_type="claim",
            entity_id=claim_id,
            action="adjudicate",
            new_value=json.dumps({"status": claim.status, "total_approved": total_approved}),
        ))
        await db.commit()


@router.post("/{claim_id}/adjudicate")
async def adjudicate_claim(
    claim_id: int,
    adjudicate_data: ClaimAdjudicate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enqueues adjudication as a background task. Returns 202 Accepted immediately.
    Poll GET /claims/{id} to check when status moves from in_adjudication.
    """
    if current_user.role not in Role.CAN_ADJUDICATE:
        raise HTTPException(status_code=403, detail="Not authorised to adjudicate claims")

    repo = ClaimRepository(db)
    claim = await repo.get_by_id(claim_id, scheme_id=_effective_scheme_id(current_user))
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status not in [ClaimStatus.RECEIVED, ClaimStatus.IN_ADJUDICATION]:
        raise HTTPException(status_code=400, detail="Claim cannot be adjudicated in its current status")

    # Transition to in_adjudication immediately so concurrent requests are blocked
    claim.status = ClaimStatus.IN_ADJUDICATION
    claim.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(_run_adjudication_background, claim_id, current_user.id)
    return {"claim_id": claim_id, "status": ClaimStatus.IN_ADJUDICATION, "message": "Adjudication queued"}


@router.post("/{claim_id}/override", response_model=ClaimResponse)
async def override_claim(
    claim_id: int,
    override_data: ClaimOverride,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_OVERRIDE_CLAIM:
        raise HTTPException(status_code=403, detail="Not authorised to override claims")

    result = await db.execute(load_claim_with_relations(db).where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    old_status = claim.status
    claim.status = override_data.override_status
    claim.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="claim",
        entity_id=claim_id,
        action="override",
        old_value=json.dumps({"status": old_status}),
        new_value=json.dumps({"status": override_data.override_status, "reason": override_data.reason}),
    )
    db.add(audit)
    await db.commit()

    result = await db.execute(load_claim_with_relations(db).where(Claim.id == claim_id))
    return result.scalar_one()


@router.get("/{claim_id}/audit-trail")
async def get_claim_audit_trail(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "claim", AuditLog.entity_id == claim_id)
        .order_by(AuditLog.timestamp.desc())
    )
    return result.scalars().all()


@router.get("/{claim_id}/adjudication-log")
async def get_adjudication_log(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the full 7-stage adjudication log for a claim, grouped by stage.
    Written by run_full_adjudication(); empty if adjudicate has not been run yet.
    """
    claim_result = await db.execute(
        select(Claim).where(Claim.id == claim_id)
    )
    claim = claim_result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    _sid = _effective_scheme_id(current_user)
    if _sid is not None and claim.scheme_id != _sid:
        raise HTTPException(status_code=404, detail="Claim not found")

    result = await db.execute(
        select(ClaimAdjudicationLog)
        .where(ClaimAdjudicationLog.claim_id == claim_id)
        .order_by(ClaimAdjudicationLog.stage, ClaimAdjudicationLog.id)
    )
    logs = result.scalars().all()

    # Group by stage number
    import json as _json
    stages: dict = {}
    for log in logs:
        stage_key = log.stage
        if stage_key not in stages:
            stages[stage_key] = {
                "stage": log.stage,
                "stage_name": log.stage_name,
                "entries": [],
            }
        stages[stage_key]["entries"].append({
            "id": log.id,
            "claim_line_id": log.claim_line_id,
            "rule_code": log.rule_code,
            "result": log.result,
            "detail": _json.loads(log.detail) if log.detail else {},
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "claim_id": claim_id,
        "stages": list(stages.values()),
    }


@router.get("/{claim_id}/rules")
async def get_claim_rules_engine(
    claim_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(load_claim_with_relations(db).where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    lines_data = [
        {
            "tariff_code": line.tariff_code,
            "billed_amount": line.billed_amount,
            "icd10_code": line.icd10_code,
        }
        for line in claim.lines
    ]

    rules = await run_rules_engine(
        db=db,
        member_id=claim.member_id,
        provider_id=claim.provider_id,
        date_of_service_from=claim.date_of_service_from,
        claim_lines=lines_data,
        claim_id=claim_id,
    )
    return rules
