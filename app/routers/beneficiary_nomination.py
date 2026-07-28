# Auto-generated async CRUD router for MemberNominee
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user, _effective_scheme_id
from app.models.auth import User
from app.schemas.beneficiary_nomination import MemberNomineeCreate, MemberNomineeUpdate, MemberNomineeRead
from app.repositories.beneficiary_nomination_repository import MemberNomineeRepository
from app.repositories.member import MemberRepository
from app.services.beneficiary_nomination_service import MemberNomineeService
from app.constants import Role

router = APIRouter(prefix="/api/v1/beneficiary-nomination", tags=["Beneficiary Nomination"])

async def get_service(db: AsyncSession = Depends(get_db)) -> MemberNomineeService:
    repo = MemberNomineeRepository(db)
    member_repo = MemberRepository(db)
    return MemberNomineeService(repo, member_repo)


@router.get("", response_model=List[MemberNomineeRead])
async def list_items(
    member_id: int,
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    # Role check: Read: any role with CAN_VIEW_MEMBER. 
    # For now, we assume all authenticated users can view if they belong to the scheme.
    scheme_id = _effective_scheme_id(current_user)
    return await service.list_nominees(member_id, scheme_id=scheme_id)


@router.post("", response_model=MemberNomineeRead, status_code=201)
async def create_item(
    payload: MemberNomineeCreate,
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    # Role check: Write: Role.SCHEME_ADMIN, Role.SUPER_ADMIN, Role.CALL_CENTRE.
    if current_user.role not in [Role.SCHEME_ADMIN, Role.SUPER_ADMIN, Role.CALL_CENTRE_AGENT]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    scheme_id = _effective_scheme_id(current_user)
    return await service.create_nominee(payload, scheme_id=scheme_id)


@router.put("/sync/{member_id}", response_model=List[MemberNomineeRead])
async def sync_items(
    member_id: int,
    payload: List[MemberNomineeCreate],
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [Role.SCHEME_ADMIN, Role.SUPER_ADMIN, Role.CALL_CENTRE_AGENT]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    scheme_id = _effective_scheme_id(current_user)
    return await service.sync_nominees(member_id, payload, scheme_id=scheme_id)


@router.get("/{item_id}", response_model=MemberNomineeRead)
async def get_item(
    item_id: int,
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    scheme_id = _effective_scheme_id(current_user)
    obj = await service.repo.get(item_id, scheme_id=scheme_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{item_id}", response_model=MemberNomineeRead)
async def update_item(
    item_id: int,
    payload: MemberNomineeUpdate,
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [Role.SCHEME_ADMIN, Role.SUPER_ADMIN, Role.CALL_CENTRE_AGENT]:
        raise HTTPException(status_code=403, detail="Permission denied")

    scheme_id = _effective_scheme_id(current_user)
    return await service.update_nominee(item_id, payload, scheme_id=scheme_id)


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    service: MemberNomineeService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [Role.SCHEME_ADMIN, Role.SUPER_ADMIN, Role.CALL_CENTRE_AGENT]:
        raise HTTPException(status_code=403, detail="Permission denied")

    scheme_id = _effective_scheme_id(current_user)
    deleted = await service.delete_nominee(item_id, scheme_id=scheme_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
