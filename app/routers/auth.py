import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Union, Optional
from datetime import timedelta, datetime, timezone
import hashlib
import hmac
import secrets

from app.config import settings
from app.database import get_db
from app.integrations.contracts import MessagingGateway
from app.integrations.registry import get as get_integration
from app.models.auth import (
    User,
    Scheme,
    UserSchemeMembership,
    PasswordResetToken,
    PasswordResetRequest,
    AuditLog,
)
from app.schemas.auth import (
    Token,
    TokenRefresh,
    UserResponse,
    SchemeOption,
    SchemePickerResponse,
    PasswordResetRequest as PasswordResetRequestPayload,
    PasswordResetConfirm,
    PasswordResetValidateRequest,
    PasswordResetValidateResponse,
)
from app.constants import PasswordResetTokenStatus
from app.auth.security import verify_password, create_access_token, create_refresh_token, decode_token, get_password_hash
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _get_rate_limit_counts(db: AsyncSession, email: str, ip_address: Optional[str]) -> tuple[int, int]:
    one_hour_ago = _utc_now() - timedelta(hours=1)
    email_count_result = await db.execute(
        select(func.count())
        .select_from(PasswordResetRequest)
        .where(func.lower(PasswordResetRequest.email) == email.lower())
        .where(PasswordResetRequest.created_at >= one_hour_ago)
    )
    email_count = email_count_result.scalar_one() or 0

    ip_count_result = await db.execute(
        select(func.count())
        .select_from(PasswordResetRequest)
        .where(PasswordResetRequest.ip_address == ip_address)
        .where(PasswordResetRequest.created_at >= one_hour_ago)
    )
    ip_count = ip_count_result.scalar_one() or 0
    return email_count, ip_count


def _get_client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


async def _send_password_reset_email(email: str, full_name: Optional[str], token: str) -> None:
    gateway = get_integration(MessagingGateway)
    reset_url = f"{settings.FRONTEND_URL}/password-reset?token={token}"
    subject = "Password reset request for Clarum Healthcare Portal"
    body_text = (
        f"Hello{(' ' + full_name) if full_name else ''},\n\n"
        "A request was received to reset the password for your Clarum Healthcare Portal account.\n"
        f"If this was you, click the link below to set a new password:\n\n"
        f"{reset_url}\n\n"
        "If you cannot click the link, copy and paste it into your browser.\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "Regards,\n"
        "Clarum Healthcare Portal Team"
    )
    body_html = (
        f"<p>Hello{(' ' + full_name) if full_name else ''},</p>"
        "<p>A request was received to reset the password for your Clarum Healthcare Portal account.</p>"
        "<p>If this was you, click the link below to set a new password:</p>"
        f"<p><a href=\"{reset_url}\">Reset password</a></p>"
        "<p>If you cannot click the link, copy and paste it into your browser.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
        "<p>Regards,<br>Clarum Healthcare Portal Team</p>"
    )
    gateway.send_email(
        to=email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
    )


async def _find_reset_token(db: AsyncSession, token: str) -> Optional[PasswordResetToken]:
    hashed = _hash_reset_token(token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hashed))
    return result.scalar_one_or_none()


async def _validate_reset_token(record: PasswordResetToken) -> None:
    if record.status != PasswordResetTokenStatus.PENDING:
        logger.warning(f"Password reset failed: Token status is {record.status}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link has already been used.")
    
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < _utc_now():
        logger.warning(f"Password reset failed: Token expired at {expires_at} (now: {_utc_now()})")
        record.status = PasswordResetTokenStatus.EXPIRED
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link has expired.")


@router.post("/password/reset-request")
async def request_password_reset(
    payload: PasswordResetRequestPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.strip().lower()
    ip_address = _get_client_ip(request)

    email_count, ip_count = await _get_rate_limit_counts(db, email, ip_address)
    rate_limited = email_count >= 3 or ip_count >= 10

    reset_request = PasswordResetRequest(email=email, ip_address=ip_address)
    db.add(reset_request)

    if not rate_limited:
        user_result = await db.execute(
            select(User).where(func.lower(User.email) == email)
        )
        user = user_result.scalar_one_or_none()
        if user and user.is_active:
            token = secrets.token_urlsafe(32)
            reset_token = PasswordResetToken(
                user_id=user.id,
                email=email,
                token_hash=_hash_reset_token(token),
                status=PasswordResetTokenStatus.PENDING,
                expires_at=_utc_now() + timedelta(minutes=30),
                ip_address=ip_address,
            )
            db.add(reset_token)
            await db.flush()
            await _send_password_reset_email(user.email, user.full_name, token)

    await db.commit()
    return {"message": "If that address exists, a reset link is on its way"}


@router.post("/password/reset/validate", response_model=PasswordResetValidateResponse)
async def validate_password_reset(
    payload: PasswordResetValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    token_record = await _find_reset_token(db, payload.token)
    if not token_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid.")
    await _validate_reset_token(token_record)
    return PasswordResetValidateResponse(valid=True)


@router.post("/password/reset", response_model=Token)
async def reset_password(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    token_record = await _find_reset_token(db, payload.token)
    if not token_record:
        logger.warning(f"Password reset failed: Token not found for token starting with {payload.token[:8]}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid.")
    await _validate_reset_token(token_record)

    user_result = await db.execute(select(User).where(User.id == token_record.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error(f"Password reset failed: User ID {token_record.user_id} not found for valid token")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid.")
    
    if not user.is_active:
        logger.warning(f"Password reset failed: User {user.email} is inactive")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid.")

    if len(payload.new_password) < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 10 characters long.")

    # Mark the reset token used and update the password.
    token_record.status = PasswordResetTokenStatus.USED
    token_record.used_at = _utc_now()
    user.hashed_password = get_password_hash(payload.new_password)
    user.must_reset_password = False

    audit = AuditLog(
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="password_reset",
        old_value="pending",
        new_value="reset",
        ip_address=None,
    )
    db.add(audit)

    await db.flush()

    memberships_result = await db.execute(
        select(UserSchemeMembership).where(UserSchemeMembership.user_id == user.id).where(UserSchemeMembership.is_active == True)
    )
    memberships = memberships_result.scalars().all()
    scheme_id = memberships[0].scheme_id if len(memberships) == 1 else user.scheme_id

    token_data = {"sub": str(user.id)}
    if scheme_id is not None:
        token_data["scheme_id"] = scheme_id

    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    await db.commit()
    return Token(access_token=access_token, refresh_token=refresh_token)


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

    memberships_result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == user.id)
        .where(UserSchemeMembership.is_active == True)
    )
    memberships = memberships_result.scalars().all()

    if len(memberships) > 1:
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


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log the logout event. The client is still responsible for clearing the token."""
    scheme_id = _effective_scheme_id(current_user)
    
    db.add(AuditLog(
        user_id=current_user.id,
        scheme_id=scheme_id,
        entity_type="user",
        entity_id=current_user.id,
        action=AuditAction.LOGOUT,
        ip_address=_get_client_ip(request),
        user_role=current_user.role
    ))
    
    await db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_user_response(current_user, db)
