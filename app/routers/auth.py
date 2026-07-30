import json
import logging
import os
import secrets
from base64 import b64encode, b64decode
from datetime import timedelta, datetime, timezone
from typing import Union, Optional

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
import hashlib
import hmac

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
    MfaSetupResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
    MfaDisableRequest,
    MfaChallengeRequest,
    MfaChallengeResponse,
    MfaRegenerateResponse,
    MfaRequiredResponse,
)
from app.constants import PasswordResetTokenStatus, MfaAuditAction
from app.auth.security import verify_password, create_access_token, create_refresh_token, decode_token, get_password_hash
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_pre_mfa_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# AES-256-GCM helpers for TOTP secret encryption
# ---------------------------------------------------------------------------

def _get_aes_key() -> bytes:
    """Return the 32-byte AES key from settings (hex-encoded)."""
    key_hex = settings.MFA_ENCRYPTION_KEY
    key_bytes = bytes.fromhex(key_hex)
    if len(key_bytes) != 32:
        raise ValueError("MFA_ENCRYPTION_KEY must be a 64-character hex string (32 bytes)")
    return key_bytes


def _encrypt_totp_secret(plaintext: str) -> str:
    """Encrypt a TOTP base32 secret with AES-256-GCM. Returns base64(nonce + ciphertext + tag)."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return b64encode(nonce + ciphertext).decode("utf-8")


def _decrypt_totp_secret(encrypted: str) -> str:
    """Decrypt an AES-256-GCM encrypted TOTP secret."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    raw = b64decode(encrypted.encode("utf-8"))
    nonce = raw[:12]
    ciphertext = raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


# ---------------------------------------------------------------------------
# Recovery code helpers
# ---------------------------------------------------------------------------

def _generate_recovery_codes() -> list[str]:
    """Generate 10 random recovery codes (12 hex chars each)."""
    return [secrets.token_hex(6) for _ in range(10)]


def _hash_recovery_code(code: str) -> str:
    """Return a bcrypt hash of a recovery code."""
    import bcrypt as _bcrypt
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(code.encode("utf-8"), salt).decode("utf-8")


def _check_recovery_code(code: str, hashed: str) -> bool:
    """Constant-time bcrypt comparison."""
    import bcrypt as _bcrypt
    try:
        return _bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pre-MFA token helpers
# ---------------------------------------------------------------------------

def _create_pre_mfa_token(user_id: int) -> str:
    """Issue a short-lived JWT (10 min) with type=pre_mfa. No scheme_id."""
    return create_access_token(
        data={"sub": str(user_id), "type": "pre_mfa"},
        expires_delta=timedelta(minutes=10),
    )


async def _get_user_from_pre_mfa_token(
    token: Optional[str],
    db: AsyncSession,
) -> User:
    """Validate a pre_mfa token and return the associated User."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pre-MFA token required")
    payload = decode_token(token)
    if not payload or payload.get("type") != "pre_mfa":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired pre-MFA token")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
        mfa_enabled=user.totp_enabled or False,
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


# ---------------------------------------------------------------------------
# Password reset endpoints
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=Union[Token, SchemePickerResponse, MfaRequiredResponse])
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

    # MFA gate — if TOTP is enabled, issue a short-lived pre-MFA token
    if user.totp_enabled:
        pre_auth_mfa_token = _create_pre_mfa_token(user.id)
        return MfaRequiredResponse(
            mfa_required=True,
            pre_auth_mfa_token=pre_auth_mfa_token,
        )

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


# ---------------------------------------------------------------------------
# Scheme selection / switching
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_user_response(current_user, db)


# ---------------------------------------------------------------------------
# MFA endpoints
# ---------------------------------------------------------------------------

@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_user),
):
    """Generate a new TOTP secret and return the otpauth:// URI.
    The secret is NOT persisted here — it is only stored after verify succeeds."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Clarum",
    )
    return MfaSetupResponse(otpauth_url=otpauth_url, secret=secret)


@router.post("/mfa/verify", response_model=MfaVerifyResponse)
async def mfa_verify(
    payload: MfaVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify the TOTP code against the provided secret, then enable MFA for the user."""
    totp = pyotp.TOTP(payload.secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    # Encrypt and persist the secret
    current_user.totp_secret_enc = _encrypt_totp_secret(payload.secret)
    current_user.totp_enabled = True
    current_user.totp_fail_count = 0
    current_user.totp_lockout_until = None

    # Generate recovery codes
    plaintext_codes = _generate_recovery_codes()
    hashed_codes = [_hash_recovery_code(c) for c in plaintext_codes]
    current_user.recovery_codes_hash = json.dumps(hashed_codes)

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        action=MfaAuditAction.ENABLED,
    )
    db.add(audit)
    await db.commit()

    return MfaVerifyResponse(enabled=True, recovery_codes=plaintext_codes)


@router.post("/mfa/disable")
async def mfa_disable(
    payload: MfaDisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA. Requires current password and a fresh TOTP code."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    if not current_user.totp_enabled or not current_user.totp_secret_enc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")

    secret = _decrypt_totp_secret(current_user.totp_secret_enc)
    totp = pyotp.TOTP(secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    current_user.totp_secret_enc = None
    current_user.totp_enabled = False
    current_user.recovery_codes_hash = None
    current_user.totp_fail_count = 0
    current_user.totp_lockout_until = None

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        action=MfaAuditAction.DISABLED,
    )
    db.add(audit)
    await db.commit()

    return {"message": "MFA has been disabled"}


@router.post("/mfa/challenge", response_model=MfaChallengeResponse)
async def mfa_challenge(
    payload: MfaChallengeRequest,
    token: Optional[str] = Depends(_pre_mfa_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Validate a TOTP code or recovery code against the pre-MFA token.
    On success, issues a full JWT pair."""
    user = await _get_user_from_pre_mfa_token(token, db)

    if not user.totp_enabled or not user.totp_secret_enc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled for this account")

    # Check lockout
    if user.totp_lockout_until:
        lockout_until = user.totp_lockout_until
        if lockout_until.tzinfo is None:
            lockout_until = lockout_until.replace(tzinfo=timezone.utc)
        if lockout_until > _utc_now():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked due to too many failed MFA attempts. Try again in 15 minutes.",
            )
        # Lockout expired — reset counters
        user.totp_fail_count = 0
        user.totp_lockout_until = None

    secret = _decrypt_totp_secret(user.totp_secret_enc)
    totp = pyotp.TOTP(secret)
    code_valid = totp.verify(payload.code, valid_window=1)

    # If TOTP fails, try recovery codes
    recovery_used_index: Optional[int] = None
    if not code_valid and user.recovery_codes_hash:
        hashes: list[str] = json.loads(user.recovery_codes_hash)
        for i, h in enumerate(hashes):
            if _check_recovery_code(payload.code, h):
                code_valid = True
                recovery_used_index = i
                break

    if not code_valid:
        user.totp_fail_count = (user.totp_fail_count or 0) + 1
        if user.totp_fail_count >= 5:
            user.totp_lockout_until = _utc_now() + timedelta(minutes=15)
            audit = AuditLog(
                user_id=user.id,
                entity_type="user",
                entity_id=user.id,
                action=MfaAuditAction.LOCKED_OUT,
            )
            db.add(audit)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to too many failed MFA attempts. Try again in 15 minutes.",
            )
        audit = AuditLog(
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            action=MfaAuditAction.CHALLENGE_FAILED,
        )
        db.add(audit)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    # Success — reset fail counters
    user.totp_fail_count = 0
    user.totp_lockout_until = None

    # If a recovery code was used, remove it from the list (one-time use)
    if recovery_used_index is not None and user.recovery_codes_hash:
        hashes = json.loads(user.recovery_codes_hash)
        hashes.pop(recovery_used_index)
        user.recovery_codes_hash = json.dumps(hashes)

    audit = AuditLog(
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action=MfaAuditAction.CHALLENGE_SUCCESS,
    )
    db.add(audit)

    # Issue full JWT pair — handle multi-scheme users
    memberships_result = await db.execute(
        select(UserSchemeMembership)
        .where(UserSchemeMembership.user_id == user.id)
        .where(UserSchemeMembership.is_active == True)
    )
    memberships = memberships_result.scalars().all()

    if len(memberships) > 1:
        # Multi-scheme: issue a pre-auth token; client will go through scheme picker
        scheme_ids = [m.scheme_id for m in memberships]
        schemes_result = await db.execute(
            select(Scheme).where(Scheme.id.in_(scheme_ids)).where(Scheme.is_active == True)
        )
        schemes = schemes_result.scalars().all()
        pre_auth_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=10),
        )
        await db.commit()
        # Return as MfaChallengeResponse but with scheme picker tokens embedded
        # The frontend checks for requires_scheme_selection in the response
        # We return a special payload that the frontend auth store handles
        return {
            "access_token": pre_auth_token,
            "refresh_token": "",
            "token_type": "bearer",
            "requires_scheme_selection": True,
            "schemes": [{"id": s.id, "name": s.name, "code": s.code} for s in schemes],
            "pre_auth_token": pre_auth_token,
        }

    scheme_id = memberships[0].scheme_id if len(memberships) == 1 else user.scheme_id
    token_data = {"sub": str(user.id)}
    if scheme_id is not None:
        token_data["scheme_id"] = scheme_id

    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    await db.commit()
    return MfaChallengeResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/mfa/recovery-codes/regenerate", response_model=MfaRegenerateResponse)
async def mfa_regenerate_recovery_codes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate 10 new recovery codes. Requires MFA to be enabled."""
    if not current_user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")

    plaintext_codes = _generate_recovery_codes()
    hashed_codes = [_hash_recovery_code(c) for c in plaintext_codes]
    current_user.recovery_codes_hash = json.dumps(hashed_codes)

    audit = AuditLog(
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        action=MfaAuditAction.CODES_REGENERATED,
    )
    db.add(audit)
    await db.commit()

    return MfaRegenerateResponse(recovery_codes=plaintext_codes)
