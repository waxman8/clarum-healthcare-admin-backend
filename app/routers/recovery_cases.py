from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import _effective_scheme_id, get_current_user, require_roles
from app.constants import Role
from app.database import get_db
from app.models.auth import User
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.schemas.recovery import (
    PaginatedRecoveryCases,
    RecoveryCaseCreate,
    RecoveryCaseRead,
    RecoveryClaimLinkCreate,
    RecoveryClaimLinkRead,
    RecoveryTransitionCreate,
)
from app.services.recovery_case_service import RecoveryCaseError, RecoveryCaseService

router = APIRouter(
    prefix="/api/v1/recovery-cases",
    tags=["Recovery Cases"],
    dependencies=[Depends(require_roles(*Role.CAN_MANAGE_RECOVERY_CASES))],
)


def _read(case, links=None, receipts=None) -> RecoveryCaseRead:
    return RecoveryCaseRead(
        id=case.id,
        recovery_type=case.recovery_type,
        status=case.status,
        third_party_name=case.third_party_name,
        third_party_reference=case.third_party_reference,
        expected_cents=case.expected_cents,
        recovered_cents=case.recovered_cents,
        outstanding_cents=case.expected_cents - case.recovered_cents,
        created_at=case.created_at,
        updated_at=case.updated_at,
        claim_links=[RecoveryClaimLinkRead.model_validate(link) for link in links or []],
        receipts=receipts or [],
    )


def _service(db: AsyncSession) -> RecoveryCaseService:
    return RecoveryCaseService(RecoveryCaseRepository(db))


def _scheme(current_user: User) -> int:
    scheme_id = _effective_scheme_id(current_user)
    if scheme_id is None:
        raise HTTPException(status_code=403, detail="A scheme context is required")
    return scheme_id


async def _invoke(awaitable):
    try:
        return await awaitable
    except RecoveryCaseError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get("", response_model=PaginatedRecoveryCases)
async def list_recovery_cases(
    recovery_type: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await RecoveryCaseRepository(db).list(_scheme(current_user), recovery_type, status, page, page_size)
    result["items"] = [_read(case) for case in result["items"]]
    return result


@router.post("", response_model=RecoveryCaseRead, status_code=201)
async def create_recovery_case(payload: RecoveryCaseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = await _invoke(_service(db).create(payload, _scheme(current_user), current_user))
    await db.commit()
    return _read(case)


@router.get("/{case_id}", response_model=RecoveryCaseRead)
async def get_recovery_case(case_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    case, links, receipts = await _invoke(_service(db).detail(case_id, _scheme(current_user)))
    return _read(case, links, receipts)


@router.post("/{case_id}/claims", response_model=RecoveryClaimLinkRead, status_code=201)
async def link_claim(case_id: int, payload: RecoveryClaimLinkCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = await _invoke(_service(db).link_claim(case_id, payload, _scheme(current_user), current_user))
    await db.commit()
    return link


@router.post("/{case_id}/transitions", response_model=RecoveryCaseRead)
async def transition_recovery_case(case_id: int, payload: RecoveryTransitionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = _service(db)
    case = await _invoke(service.transition(case_id, payload, _scheme(current_user), current_user))
    await db.commit()
    _, links, receipts = await _invoke(service.detail(case_id, _scheme(current_user)))
    return _read(case, links, receipts)
