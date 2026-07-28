from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.database import get_db
from app.auth.dependencies import get_current_user, require_roles
from app.models.auth import User
from app.constants import Role
from app.schemas.user import UserCreate, UserUpdate, UserRead
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

router = APIRouter(
    prefix="/api/v1/users",
    tags=["User Management"],
    dependencies=[Depends(require_roles(Role.SUPER_ADMIN, Role.SCHEME_ADMIN))],
)


class UserListResponse(UserRead.__base__ or object):
    items: List[UserRead]
    total: int


@router.get("", response_model=dict)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    service = UserService(repo, db)
    users, total = await service.list_users(
        current_user=current_user,
        search=search,
        role=role,
        status=status,
        skip=skip,
        limit=limit,
    )
    return {"items": [UserRead.model_validate(u) for u in users], "total": total}


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    service = UserService(repo, db)
    user = await service.create_user(payload, current_user)
    await db.commit()
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    service = UserService(repo, db)
    user = await service.get_user(user_id, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    service = UserService(repo, db)
    user = await service.update_user(user_id, payload, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password")
async def force_password_reset(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    service = UserService(repo, db)
    success = await service.force_password_reset(user_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return {"message": "Password reset email sent successfully"}
