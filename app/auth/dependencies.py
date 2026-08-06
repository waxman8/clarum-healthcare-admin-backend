from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.database import get_db
from app.models.auth import User
from app.auth.security import decode_token
from app.constants import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ROLE_HIERARCHY = Role.ALL


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    # Attach session-scoped scheme_id from JWT (non-mapped attribute — safe from SQLAlchemy autoflush)
    scheme_id_from_token = payload.get("scheme_id")
    user._session_scheme_id = int(scheme_id_from_token) if scheme_id_from_token is not None else None

    return user


def _effective_scheme_id(current_user: User) -> Optional[int]:
    """Return the effective scheme_id for filtering queries.

    Returns the session-scoped scheme_id (from JWT) when available, otherwise
    falls back to the DB-stored scheme_id.  Returns None for super_admin users
    with no scheme assigned — callers should skip the filter when None so
    super_admins see all data.
    """
    return getattr(current_user, "_session_scheme_id", None) or current_user.scheme_id


def _scheme_id_for(current_user: User, requested_scheme_id: Optional[int] = None) -> int:
    """Resolve the scheme_id for a request.

    Priority order:
    1. SUPER_ADMIN with an explicit query-param override (requested_scheme_id)
    2. Session-scoped scheme_id from the JWT (_session_scheme_id set by get_current_user)
    3. User.scheme_id from the DB (single-scheme users and backward compat)
    """
    if current_user.role == Role.SUPER_ADMIN and requested_scheme_id:
        return requested_scheme_id

    session_sid = getattr(current_user, "_session_scheme_id", None)
    if session_sid is not None:
        return session_sid

    if not current_user.scheme_id:
        raise HTTPException(status_code=403, detail="User has no scheme assigned")
    return current_user.scheme_id


def require_roles(*roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return current_user
    return role_checker


def check_permissions(required_permissions_roles: list):
    async def permission_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_permissions_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Insufficient permissions.",
            )
        return current_user
    return permission_checker
