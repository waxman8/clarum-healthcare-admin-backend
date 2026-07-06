from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Union
from datetime import timedelta
from app.database import get_db
from app.models.auth import User, Scheme, UserSchemeMembership
from app.schemas.auth import Token, TokenRefresh, UserResponse, SchemeOption, SchemePickerResponse
from app.auth.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SchemeSelectRequest(BaseModel):
    scheme_id: int


async def build_user_response(user: User, db: AsyncSession) -> UserResponse:
    # Use session-scoped scheme_id from JWT when available (TPA users)
    effective_scheme_id = getattr(user, "_session_scheme_id", None) or user.scheme_id

    scheme_name = None
    scheme_code = None
    if effective_scheme_id:
        result = await db.execute(select(Scheme).where(Scheme.id == effective_scheme_id))
        scheme = result.scalar_one_or_none()
        if scheme:
            scheme_name = scheme.name
            scheme_code = scheme.code

    # Load available schemes for multi-scheme users (drives switcher in UI)
    memberships_result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == user.id)
        .where(UserSchemeMembership.is_active == True)
    )
    memberships = memberships_result.scalars().all()

    available_schemes: list[SchemeOption] = []
    if len(memberships) > 1:
        scheme_ids = [m.scheme_id for m in memberships]
        schemes_result = await db.execute(
            select(Scheme).where(Scheme.id.in_(scheme_ids)).where(Scheme.is_active == True)
        )
        available_schemes = [
            SchemeOption(id=s.id, name=s.name, code=s.code)
            for s in schemes_result.scalars().all()
        ]

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        scheme_id=effective_scheme_id,
        scheme_name=scheme_name,
        scheme_code=scheme_code,
        created_at=user.created_at,
        available_schemes=available_schemes,
    )


@router.post("/login", response_model=Union[Token, SchemePickerResponse])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    # Resolve which schemes this user can access
    memberships_result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == user.id)
        .where(UserSchemeMembership.is_active == True)
    )
    memberships = memberships_result.scalars().all()

    if len(memberships) > 1:
        # TPA user with multiple schemes — return picker, no full JWT yet
        scheme_ids = [m.scheme_id for m in memberships]
        schemes_result = await db.execute(
            select(Scheme).where(Scheme.id.in_(scheme_ids)).where(Scheme.is_active == True)
        )
        schemes = schemes_result.scalars().all()
        pre_auth_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=10),
        )
        return SchemePickerResponse(
            requires_scheme_selection=True,
            schemes=[SchemeOption(id=s.id, name=s.name, code=s.code) for s in schemes],
            pre_auth_token=pre_auth_token,
        )

    # Single-scheme or no-membership user — embed scheme_id in JWT
    scheme_id = memberships[0].scheme_id if len(memberships) == 1 else user.scheme_id
    token_data = {"sub": str(user.id)}
    if scheme_id is not None:
        token_data["scheme_id"] = scheme_id

    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/select-scheme", response_model=Token)
async def select_scheme(
    body: SchemeSelectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a pre-auth token + scheme selection for a full scheme-scoped JWT."""
    result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == current_user.id)
        .where(UserSchemeMembership.scheme_id == body.scheme_id)
        .where(UserSchemeMembership.is_active == True)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access to this scheme is not permitted")

    token_data = {"sub": str(current_user.id), "scheme_id": body.scheme_id}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/switch-scheme", response_model=Token)
async def switch_scheme(
    body: SchemeSelectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-issue a JWT scoped to a different scheme. Requires an active session."""
    result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == current_user.id)
        .where(UserSchemeMembership.scheme_id == body.scheme_id)
        .where(UserSchemeMembership.is_active == True)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access to this scheme is not permitted")

    token_data = {"sub": str(current_user.id), "scheme_id": body.scheme_id}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: TokenRefresh,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    scheme_id = payload.get("scheme_id")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_data = {"sub": str(user.id)}
    if scheme_id is not None:
        token_data["scheme_id"] = scheme_id

    access_token = create_access_token(data=token_data)
    new_refresh = create_refresh_token(data=token_data)
    return Token(access_token=access_token, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_user_response(current_user, db)
