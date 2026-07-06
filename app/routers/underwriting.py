from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel as _BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
import math

from app.database import get_db
from app.models.underwriting import UnderwritingDecision, MemberConditionExclusion
from app.models.members import Member
from app.schemas.underwriting import (
    UnderwritingDecisionCreate,
    UnderwritingDecisionUpdate,
    UnderwritingDecisionResponse,
    UnderwritingPreviewRequest,
    UnderwritingPreviewResponse,
    PaginatedUnderwritingResponse,
    MemberSlimResponse,
)
from app.auth.dependencies import get_current_user, _effective_scheme_id, _scheme_id_for
from app.models.auth import User
from app.models.underwriting import EnrollmentQuestionnaire
from app.schemas.underwriting import (
    EnrollmentQuestionnaireCreate,
    EnrollmentQuestionnaireResponse,
)
from app.services.underwriting import create_decision, compute_wp_and_penalty, process_questionnaire
from app.constants import Role

router = APIRouter(prefix="/api/v1/underwriting", tags=["underwriting"])

# Roles permitted to create / update decisions
UNDERWRITING_WRITE_ROLES = [
    Role.SUPER_ADMIN,
    Role.SCHEME_ADMIN,
    Role.AUTHORISATION_OFFICER,
    Role.CALL_CENTRE_AGENT,
]


def _decision_query(scheme_id: Optional[int]):
    q = (
        select(UnderwritingDecision)
        .options(selectinload(UnderwritingDecision.condition_exclusions))
    )
    if scheme_id is not None:
        q = q.where(UnderwritingDecision.scheme_id == scheme_id)
    return q


async def _attach_member(db: AsyncSession, decision: UnderwritingDecision) -> UnderwritingDecisionResponse:
    """Build the response, attaching a slim member object."""
    member_result = await db.execute(
        select(Member).where(Member.id == decision.member_id)
    )
    member = member_result.scalar_one_or_none()
    resp = UnderwritingDecisionResponse.model_validate(decision)
    if member:
        resp.member = MemberSlimResponse.model_validate(member)
    return resp


# ---------------------------------------------------------------------------
# Preview (non-persisting compute) — must be registered before /{id} routes
# ---------------------------------------------------------------------------

@router.post("/decisions/preview", response_model=UnderwritingPreviewResponse)
async def preview_decision(
    preview: UnderwritingPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Compute waiting period end date and late-joiner penalty without persisting.

    Called by the new decision form on change to show computed outputs before submit.
    """
    return compute_wp_and_penalty(
        effective_date=preview.effective_date,
        has_prior_cover=preview.has_prior_cover,
        prior_cover_break_days=preview.prior_cover_break_days,
        is_late_joiner=preview.is_late_joiner,
        late_joiner_uncovered_years=preview.late_joiner_uncovered_years,
        base_monthly_contribution=preview.base_monthly_contribution,
    )


# ---------------------------------------------------------------------------
# Decision CRUD
# ---------------------------------------------------------------------------

@router.post("/decisions", response_model=UnderwritingDecisionResponse, status_code=201)
async def create_underwriting_decision(
    data: UnderwritingDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in UNDERWRITING_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions to create underwriting decisions")

    scheme_id = _scheme_id_for(current_user)
    decision = await create_decision(db, data, scheme_id, created_by=current_user.id)
    return await _attach_member(db, decision)


@router.get("/decisions", response_model=PaginatedUnderwritingResponse)
async def list_decisions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    decision: Optional[str] = None,
    status: Optional[str] = None,
    member_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _effective_scheme_id(current_user)
    query = _decision_query(sid)

    if decision:
        query = query.where(UnderwritingDecision.decision == decision)
    if status:
        query = query.where(UnderwritingDecision.status == status)
    if member_id:
        query = query.where(UnderwritingDecision.member_id == member_id)

    query = query.order_by(UnderwritingDecision.decision_date.desc(), UnderwritingDecision.id.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    decisions = result.scalars().all()

    # Attach slim member data
    items = []
    for d in decisions:
        items.append(await _attach_member(db, d))

    return PaginatedUnderwritingResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/decisions/{decision_id}", response_model=UnderwritingDecisionResponse)
async def get_decision(
    decision_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _effective_scheme_id(current_user)
    query = _decision_query(sid).where(UnderwritingDecision.id == decision_id)
    result = await db.execute(query)
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Underwriting decision not found")
    return await _attach_member(db, decision)


@router.patch("/decisions/{decision_id}", response_model=UnderwritingDecisionResponse)
async def update_decision(
    decision_id: int,
    data: UnderwritingDecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update audit fields only (notes, override_reason). Decisions are otherwise immutable."""
    if current_user.role not in UNDERWRITING_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    sid = _effective_scheme_id(current_user)
    query = _decision_query(sid).where(UnderwritingDecision.id == decision_id)
    result = await db.execute(query)
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Underwriting decision not found")

    if data.notes is not None:
        decision.notes = data.notes
    if data.override_reason is not None:
        decision.override_reason = data.override_reason

    await db.commit()
    return await _attach_member(db, decision)


# ---------------------------------------------------------------------------
# Active underwriting profile for a member
# ---------------------------------------------------------------------------

@router.get("/members/{member_id}", response_model=UnderwritingDecisionResponse)
async def get_member_underwriting_profile(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active underwriting decision + active condition exclusions for a member."""
    sid = _effective_scheme_id(current_user)
    query = (
        select(UnderwritingDecision)
        .options(selectinload(UnderwritingDecision.condition_exclusions))
        .where(
            UnderwritingDecision.member_id == member_id,
            UnderwritingDecision.status == "active",
        )
    )
    if sid is not None:
        query = query.where(UnderwritingDecision.scheme_id == sid)

    result = await db.execute(query)
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="No active underwriting decision for this member")
    return await _attach_member(db, decision)


# ---------------------------------------------------------------------------
# Enrollment Questionnaire — triggers auto-underwriting engine
# ---------------------------------------------------------------------------

class _SubmitResponse(_BaseModel):
    questionnaire: EnrollmentQuestionnaireResponse
    decision: UnderwritingDecisionResponse


@router.post("/questionnaires", response_model=_SubmitResponse, status_code=201)
async def submit_questionnaire(
    data: EnrollmentQuestionnaireCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an enrollment questionnaire. The engine evaluates it immediately and
    returns the resulting underwriting decision alongside the questionnaire record."""
    if current_user.role not in UNDERWRITING_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    scheme_id = _scheme_id_for(current_user)
    try:
        questionnaire, decision = await process_questionnaire(
            db, data, scheme_id, created_by=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    decision_resp = await _attach_member(db, decision)
    return _SubmitResponse(
        questionnaire=EnrollmentQuestionnaireResponse.model_validate(questionnaire),
        decision=decision_resp,
    )


@router.get("/questionnaires/member/{member_id}", response_model=list[EnrollmentQuestionnaireResponse])
async def list_member_questionnaires(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all questionnaires for a member (most recent first)."""
    sid = _effective_scheme_id(current_user)
    query = (
        select(EnrollmentQuestionnaire)
        .where(EnrollmentQuestionnaire.member_id == member_id)
        .order_by(EnrollmentQuestionnaire.completed_at.desc())
    )
    if sid is not None:
        query = query.where(EnrollmentQuestionnaire.scheme_id == sid)
    result = await db.execute(query)
    return result.scalars().all()
