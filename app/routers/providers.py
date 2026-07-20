from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
import math
import json
from datetime import date, datetime, timezone

from app.database import get_db
from app.models.providers import Provider
from app.models.reference import DisciplineCode
from app.models.auth import User
from app.schemas.providers import (
    ProviderCreate, ProviderUpdate, BlacklistRequest,
    ProviderResponse, ProviderSummaryResponse, PaginatedProvidersResponse,
    DisciplineCodeResponse,
)
from app.auth.dependencies import get_current_user
from app.constants import Role
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])

BANKING_ROLES = [Role.SUPER_ADMIN, Role.FINANCE_OFFICER]


def _strip_banking(provider: Provider, current_user: User) -> ProviderResponse:
    """Return full ProviderResponse, zeroing banking fields for non-finance roles."""
    resp = ProviderResponse.model_validate(provider)
    if current_user.role not in BANKING_ROLES:
        resp.bank_name = None
        resp.branch_code = None
        resp.account_number = None
        resp.account_type = None
        resp.account_holder = None
    return resp


# ---------------------------------------------------------------------------
# Discipline codes (reference, platform-wide)
# ---------------------------------------------------------------------------

@router.get("/discipline-codes", response_model=List[DisciplineCodeResponse])
async def list_discipline_codes(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all BHF discipline codes, optionally filtered by category."""
    query = select(DisciplineCode).where(DisciplineCode.is_active == True)  # noqa: E712
    if category:
        query = query.where(DisciplineCode.category == category)
    query = query.order_by(DisciplineCode.code)
    result = await db.execute(query)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Provider CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=ProviderResponse)
async def create_provider(
    provider_data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    existing = (await db.execute(
        select(Provider).where(Provider.practice_number == provider_data.practice_number)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Practice number already registered")

    provider = Provider(**provider_data.model_dump())
    db.add(provider)
    await db.flush()
    log_audit(
        db, "provider", provider.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=provider.trading_name,
        new_value=json.dumps({"practice_number": provider.practice_number}, default=str),
    )
    await db.commit()
    await db.refresh(provider)
    return _strip_banking(provider, current_user)


@router.get("", response_model=PaginatedProvidersResponse)
async def list_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    provider_category: Optional[str] = None,
    discipline_code: Optional[str] = None,
    province: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_blacklisted: Optional[bool] = None,
    contracted: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Provider)

    if search:
        query = query.where(
            or_(
                Provider.trading_name.ilike(f"%{search}%"),
                Provider.registered_name.ilike(f"%{search}%"),
                Provider.practice_number.ilike(f"%{search}%"),
                Provider.hpcsa_number.ilike(f"%{search}%"),
            )
        )
    if provider_category:
        query = query.where(Provider.provider_category == provider_category)
    if discipline_code:
        query = query.where(Provider.discipline_code == discipline_code)
    if province:
        query = query.where(Provider.province == province)
    if is_active is not None:
        query = query.where(Provider.is_active == is_active)
    if is_blacklisted is not None:
        query = query.where(Provider.is_blacklisted == is_blacklisted)
    if contracted is not None:
        query = query.where(Provider.contracted == contracted)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Provider.trading_name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    providers = result.scalars().all()

    return PaginatedProvidersResponse(
        items=providers,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _strip_banking(provider, current_user)


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    provider_data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [Role.SUPER_ADMIN, Role.SCHEME_ADMIN, Role.FINANCE_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = provider_data.model_dump(exclude_unset=True)

    # Banking fields: only finance_admin / super_admin may update
    banking_fields = {"bank_name", "branch_code", "account_number", "account_type", "account_holder"}
    if any(f in update_data for f in banking_fields) and current_user.role not in BANKING_ROLES:
        raise HTTPException(status_code=403, detail="Banking details require finance_admin role")

    old_values = {field: getattr(provider, field) for field in update_data}
    for field, value in update_data.items():
        setattr(provider, field, value)

    provider.updated_at = datetime.now(timezone.utc)
    provider.modified_date = datetime.now(timezone.utc)
    provider.modified_user = current_user.id

    if update_data:
        log_audit(
            db, "provider", provider.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=provider.trading_name,
            old_value=json.dumps(old_values, default=str),
            new_value=json.dumps(update_data, default=str),
        )
    await db.commit()
    await db.refresh(provider)
    return _strip_banking(provider, current_user)


@router.post("/{provider_id}/blacklist", response_model=ProviderResponse)
async def blacklist_provider(
    provider_id: int,
    request: BlacklistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flag a provider as blacklisted. super_admin only."""
    if current_user.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="super_admin required")

    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.is_blacklisted = True
    provider.blacklist_reason = request.reason
    provider.blacklist_date = request.blacklist_date or date.today()
    provider.is_active = False
    provider.updated_at = datetime.now(timezone.utc)
    provider.modified_date = datetime.now(timezone.utc)
    provider.modified_user = current_user.id
    log_audit(
        db, "provider", provider.id, "blacklist",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=provider.trading_name,
        new_value=json.dumps({"reason": request.reason}, default=str),
    )
    await db.commit()
    await db.refresh(provider)
    return _strip_banking(provider, current_user)


@router.post("/{provider_id}/unblacklist", response_model=ProviderResponse)
async def unblacklist_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove blacklist flag. super_admin only."""
    if current_user.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="super_admin required")

    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.is_blacklisted = False
    provider.blacklist_reason = None
    provider.blacklist_date = None
    provider.is_active = True
    provider.updated_at = datetime.now(timezone.utc)
    provider.modified_date = datetime.now(timezone.utc)
    provider.modified_user = current_user.id
    log_audit(
        db, "provider", provider.id, "unblacklist",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=provider.trading_name,
    )
    await db.commit()
    await db.refresh(provider)
    return _strip_banking(provider, current_user)


@router.get("/{provider_id}/networks")
async def get_provider_networks(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all network designations for this provider across schemes."""
    from app.models.billing import ProviderNetwork
    from app.models.auth import Scheme
    from sqlalchemy.orm import selectinload

    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    result = await db.execute(
        select(ProviderNetwork)
        .options(selectinload(ProviderNetwork.scheme))
        .where(ProviderNetwork.provider_id == provider_id)
        .order_by(ProviderNetwork.effective_from.desc())
    )
    networks = result.scalars().all()
    return [
        {
            "id": n.id,
            "scheme_id": n.scheme_id,
            "scheme": {"name": n.scheme.name, "code": n.scheme.code} if n.scheme else None,
            "network_type": n.network_type,
            "effective_from": str(n.effective_from),
            "effective_to": str(n.effective_to) if n.effective_to else None,
        }
        for n in networks
    ]


@router.delete("/{provider_id}")
async def deactivate_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete (deactivate) a provider."""
    if current_user.role not in [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    provider = (await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.is_active = False
    provider.updated_at = datetime.now(timezone.utc)
    provider.modified_date = datetime.now(timezone.utc)
    provider.modified_user = current_user.id
    log_audit(
        db, "provider", provider.id, "deactivate",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=provider.trading_name,
    )
    await db.commit()
    return {"message": "Provider deactivated"}
