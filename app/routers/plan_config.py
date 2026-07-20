"""
Plan configuration router — scheme-specific plan, benefit, and network settings.
All endpoints are scoped to the authenticated user's scheme (except SUPER_ADMIN who can pass scheme_id).
Write endpoints require SUPER_ADMIN or SCHEME_ADMIN.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
import math
import json

from app.database import get_db
from app.models.reference import PlanOption
from app.models.members import BenefitLimit
from app.models.billing import ContributionRate, CopaymentRule, Formulary, NappiCode, ProviderNetwork
from app.models.providers import Provider
from app.models.auth import User
from app.schemas.plan_config import (
    PlanOptionCreate, PlanOptionUpdate, PlanOptionResponse,
    BenefitLimitCreate, BenefitLimitUpdate, BenefitLimitResponse, PaginatedBenefitLimitResponse,
    ContributionRateCreate, ContributionRateUpdate, ContributionRateResponse,
    CopaymentRuleCreate, CopaymentRuleUpdate, CopaymentRuleResponse,
    FormularyCreate, FormularyUpdate, FormularyResponse, PaginatedFormularyResponse,
    ProviderNetworkCreate, ProviderNetworkUpdate, ProviderNetworkResponse, PaginatedProviderNetworkResponse,
)
from app.auth.dependencies import get_current_user, _scheme_id_for
from app.constants import Role
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/plan-config", tags=["plan-config"])

ADMIN_ROLES = [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]


def _require_admin(current_user: User):
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")


# ===========================================================================
# Plan Options
# ===========================================================================

@router.get("/plans", response_model=List[PlanOptionResponse])
async def list_plan_options(
    scheme_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(PlanOption).where(PlanOption.scheme_id == sid)
    if is_active is not None:
        query = query.where(PlanOption.is_active == is_active)
    result = await db.execute(query.order_by(PlanOption.name))
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=PlanOptionResponse)
async def get_plan_option(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(PlanOption).where(PlanOption.id == plan_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Plan option not found")
    sid = _scheme_id_for(current_user)
    if current_user.role != Role.SUPER_ADMIN and obj.scheme_id != sid:
        raise HTTPException(status_code=403, detail="Access denied")
    return obj


@router.post("/plans", response_model=PlanOptionResponse, status_code=201)
async def create_plan_option(
    data: PlanOptionCreate,
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    sid = _scheme_id_for(current_user, scheme_id)
    obj = PlanOption(scheme_id=sid, **data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "plan_option", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, scheme_id=sid, entity_label=obj.name,
        new_value=json.dumps({"name": obj.name}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/plans/{plan_id}", response_model=PlanOptionResponse)
async def update_plan_option(
    plan_id: int,
    data: PlanOptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(PlanOption).where(PlanOption.id == plan_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Plan option not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "plan_option", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id, entity_label=obj.name,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan_option(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(PlanOption).where(PlanOption.id == plan_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Plan option not found")
    log_audit(
        db, "plan_option", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id, entity_label=obj.name,
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Benefit Limits
# ===========================================================================

@router.get("/benefit-limits", response_model=PaginatedBenefitLimitResponse)
async def list_benefit_limits(
    plan_option_id: Optional[int] = None,
    benefit_year: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(BenefitLimit).join(PlanOption).where(PlanOption.scheme_id == sid)
    if plan_option_id:
        query = query.where(BenefitLimit.plan_option_id == plan_option_id)
    if benefit_year:
        query = query.where(BenefitLimit.benefit_year == benefit_year)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(BenefitLimit.benefit_category).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedBenefitLimitResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/benefit-limits", response_model=BenefitLimitResponse, status_code=201)
async def create_benefit_limit(
    data: BenefitLimitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = BenefitLimit(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "benefit_limit", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=f"{obj.benefit_category} ({obj.limit_type})",
        new_value=json.dumps({"limit_value": obj.limit_value, "benefit_year": obj.benefit_year}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/benefit-limits/{limit_id}", response_model=BenefitLimitResponse)
async def update_benefit_limit(
    limit_id: int,
    data: BenefitLimitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(BenefitLimit).where(BenefitLimit.id == limit_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Benefit limit not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "benefit_limit", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"{obj.benefit_category} ({obj.limit_type})",
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/benefit-limits/{limit_id}", status_code=204)
async def delete_benefit_limit(
    limit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(BenefitLimit).where(BenefitLimit.id == limit_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Benefit limit not found")
    log_audit(
        db, "benefit_limit", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=f"{obj.benefit_category} ({obj.limit_type})",
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Contribution Rates
# ===========================================================================

@router.get("/contribution-rates", response_model=List[ContributionRateResponse])
async def list_contribution_rates(
    plan_option_id: Optional[int] = None,
    effective_year: Optional[int] = None,
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(ContributionRate).join(PlanOption).where(PlanOption.scheme_id == sid)
    if plan_option_id:
        query = query.where(ContributionRate.plan_option_id == plan_option_id)
    if effective_year:
        query = query.where(ContributionRate.effective_year == effective_year)
    result = await db.execute(query.order_by(ContributionRate.plan_option_id, ContributionRate.member_type))
    return result.scalars().all()


@router.post("/contribution-rates", response_model=ContributionRateResponse, status_code=201)
async def create_contribution_rate(
    data: ContributionRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = ContributionRate(**data.model_dump())
    db.add(obj)
    try:
        await db.flush()
        log_audit(
            db, "contribution_rate", obj.id, "create",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"Plan {obj.plan_option_id} - {obj.member_type} ({obj.effective_year})",
            new_value=json.dumps({"monthly_rate_cents": obj.monthly_rate_cents}, default=str),
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate contribution rate for this plan/member_type/year")
    await db.refresh(obj)
    return obj


@router.put("/contribution-rates/{rate_id}", response_model=ContributionRateResponse)
async def update_contribution_rate(
    rate_id: int,
    data: ContributionRateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ContributionRate).where(ContributionRate.id == rate_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Contribution rate not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "contribution_rate", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"Plan {obj.plan_option_id} - {obj.member_type} ({obj.effective_year})",
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/contribution-rates/{rate_id}", status_code=204)
async def delete_contribution_rate(
    rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ContributionRate).where(ContributionRate.id == rate_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Contribution rate not found")
    log_audit(
        db, "contribution_rate", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=f"Plan {obj.plan_option_id} - {obj.member_type} ({obj.effective_year})",
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Copayment Rules
# ===========================================================================

@router.get("/copayment-rules", response_model=List[CopaymentRuleResponse])
async def list_copayment_rules(
    plan_option_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(CopaymentRule).where(CopaymentRule.scheme_id == sid)
    if plan_option_id is not None:
        query = query.where(CopaymentRule.plan_option_id == plan_option_id)
    if is_active is not None:
        query = query.where(CopaymentRule.is_active == is_active)
    result = await db.execute(query.order_by(CopaymentRule.trigger))
    return result.scalars().all()


@router.post("/copayment-rules", response_model=CopaymentRuleResponse, status_code=201)
async def create_copayment_rule(
    data: CopaymentRuleCreate,
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    sid = _scheme_id_for(current_user, scheme_id)
    obj = CopaymentRule(scheme_id=sid, **data.model_dump())
    db.add(obj)
    try:
        await db.flush()
        log_audit(
            db, "copayment_rule", obj.id, "create",
            user_id=current_user.id, user_role=current_user.role, scheme_id=sid, entity_label=obj.trigger,
            new_value=json.dumps({"trigger": obj.trigger}, default=str),
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate trigger for this scheme/plan")
    await db.refresh(obj)
    return obj


@router.put("/copayment-rules/{rule_id}", response_model=CopaymentRuleResponse)
async def update_copayment_rule(
    rule_id: int,
    data: CopaymentRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(CopaymentRule).where(CopaymentRule.id == rule_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Copayment rule not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "copayment_rule", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id, entity_label=obj.trigger,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/copayment-rules/{rule_id}", status_code=204)
async def delete_copayment_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(CopaymentRule).where(CopaymentRule.id == rule_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Copayment rule not found")
    log_audit(
        db, "copayment_rule", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id, entity_label=obj.trigger,
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Formulary
# ===========================================================================

@router.get("/formulary", response_model=PaginatedFormularyResponse)
async def list_formulary(
    plan_option_id: Optional[int] = None,
    formulary_type: Optional[str] = None,
    effective_year: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(Formulary).join(PlanOption).where(PlanOption.scheme_id == sid)
    if plan_option_id:
        query = query.where(Formulary.plan_option_id == plan_option_id)
    if formulary_type:
        query = query.where(Formulary.formulary_type == formulary_type)
    if effective_year:
        query = query.where(Formulary.effective_year == effective_year)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(Formulary.formulary_type, Formulary.id).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedFormularyResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/formulary", response_model=FormularyResponse, status_code=201)
async def create_formulary_entry(
    data: FormularyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = Formulary(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "formulary", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=f"Plan {obj.plan_option_id} - {obj.formulary_type}",
        new_value=json.dumps({"nappi_code_id": obj.nappi_code_id}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/formulary/{entry_id}", response_model=FormularyResponse)
async def update_formulary_entry(
    entry_id: int,
    data: FormularyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(Formulary).where(Formulary.id == entry_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Formulary entry not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "formulary", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"Plan {obj.plan_option_id} - {obj.formulary_type}",
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/formulary/{entry_id}", status_code=204)
async def delete_formulary_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(Formulary).where(Formulary.id == entry_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Formulary entry not found")
    log_audit(
        db, "formulary", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role,
        entity_label=f"Plan {obj.plan_option_id} - {obj.formulary_type}",
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Provider Networks
# ===========================================================================

@router.get("/provider-networks", response_model=PaginatedProviderNetworkResponse)
async def list_provider_networks(
    provider_id: Optional[int] = None,
    network_type: Optional[str] = None,
    active_only: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user, scheme_id)
    query = select(ProviderNetwork).where(ProviderNetwork.scheme_id == sid)
    if provider_id:
        query = query.where(ProviderNetwork.provider_id == provider_id)
    if network_type:
        query = query.where(ProviderNetwork.network_type == network_type)
    if active_only:
        query = query.where(ProviderNetwork.effective_to == None)  # noqa: E711

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(ProviderNetwork.network_type).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedProviderNetworkResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/provider-networks", response_model=ProviderNetworkResponse, status_code=201)
async def create_provider_network(
    data: ProviderNetworkCreate,
    scheme_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    sid = _scheme_id_for(current_user, scheme_id)
    # Verify provider exists
    provider = (await db.execute(select(Provider).where(Provider.id == data.provider_id))).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    obj = ProviderNetwork(scheme_id=sid, **data.model_dump())
    db.add(obj)
    try:
        await db.flush()
        log_audit(
            db, "provider_network", obj.id, "create",
            user_id=current_user.id, user_role=current_user.role, scheme_id=sid,
            entity_label=f"{provider.trading_name} - {obj.network_type}",
            new_value=json.dumps({"network_type": obj.network_type}, default=str),
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Provider already has this network type for this scheme")
    await db.refresh(obj)
    return obj


@router.put("/provider-networks/{network_id}", response_model=ProviderNetworkResponse)
async def update_provider_network(
    network_id: int,
    data: ProviderNetworkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ProviderNetwork).where(ProviderNetwork.id == network_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Provider network not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "provider_network", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id,
            entity_label=obj.network_type,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/provider-networks/{network_id}", status_code=204)
async def delete_provider_network(
    network_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ProviderNetwork).where(ProviderNetwork.id == network_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Provider network not found")
    log_audit(
        db, "provider_network", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, scheme_id=obj.scheme_id, entity_label=obj.network_type,
    )
    await db.delete(obj)
    await db.commit()
