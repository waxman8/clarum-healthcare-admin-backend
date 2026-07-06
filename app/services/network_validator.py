"""Network validator service.

Checks whether a provider is in the required network for a given plan and claim type,
and calculates any co-payments triggered by network non-compliance.

Design principle: all co-payment values come from the copayment_rules table.
No percentages or rand amounts are hardcoded here.

Co-payment trigger names match the copayment_rules.trigger column values seeded
by seed_medshield.py and any other scheme seeds.
"""
from datetime import date
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import CopaymentRule, ProviderNetwork


# Mapping: benefit_category → DSP trigger name for non-DSP co-payment
DSP_TRIGGER_MAP = {
    "CHRONIC_MEDICINE": "NON_NETWORK_CHRONIC_PHARMACY",
    "HIV_AIDS": "NON_DSP_HIV_MEDICATION",
    "CHRONIC_RENAL_DIALYSIS": "NON_DSP_CHRONIC_RENAL_DIALYSIS",
    "ONCOLOGY": "NON_DSP_ONCOLOGY",
    "ONCOLOGY_PET_SCAN": "NON_DSP_PET_SCAN",
    "PROSTHESIS_INTERNAL": None,  # Clinical protocol — handled manually
}

# Benefit categories that require DSP usage
DSP_REQUIRED_CATEGORIES = set(DSP_TRIGGER_MAP.keys())


async def get_provider_network_types(
    db: AsyncSession,
    provider_id: int,
    scheme_id: int,
    service_date: date,
) -> list[str]:
    """
    Return the list of network types this provider belongs to
    for the given scheme on the given service date.
    """
    result = await db.execute(
        select(ProviderNetwork.network_type).where(
            and_(
                ProviderNetwork.provider_id == provider_id,
                ProviderNetwork.scheme_id == scheme_id,
                ProviderNetwork.effective_from <= service_date,
                or_(
                    ProviderNetwork.effective_to == None,  # noqa: E711
                    ProviderNetwork.effective_to >= service_date,
                ),
            )
        )
    )
    return [row[0] for row in result.all()]


async def calculate_copayment(
    db: AsyncSession,
    scheme_id: int,
    plan_option_id: int,
    trigger: str,
    billed_amount_cents: int,
) -> int:
    """
    Look up co-payment for a given trigger and calculate the amount in cents.

    Resolution order:
    1. Plan-specific rule (plan_option_id = plan_option_id, trigger = trigger)
    2. Scheme-wide rule (plan_option_id IS NULL, trigger = trigger)
    3. No rule found → 0

    Returns co-payment amount in cents.
    """
    result = await db.execute(
        select(CopaymentRule).where(
            and_(
                CopaymentRule.scheme_id == scheme_id,
                or_(
                    CopaymentRule.plan_option_id == plan_option_id,
                    CopaymentRule.plan_option_id == None,  # noqa: E711
                ),
                CopaymentRule.trigger == trigger,
                CopaymentRule.is_active == True,  # noqa: E712
            )
        ).order_by(
            # Plan-specific (not NULL) takes precedence over scheme-wide (NULL)
            CopaymentRule.plan_option_id.nulls_last()
        )
    )
    rules = result.scalars().all()
    if not rules:
        return 0

    rule = rules[0]  # Best match after ordering

    if rule.copayment_type == "PERCENTAGE":
        # copayment_value stored as integer percentage (e.g. 20 = 20%)
        return int(billed_amount_cents * rule.copayment_value / 100)
    elif rule.copayment_type == "RAND_AMOUNT":
        # copayment_value stored in cents
        return rule.copayment_value
    return 0


async def check_hospital_network(
    db: AsyncSession,
    provider_id: int,
    scheme_id: int,
    plan_option_id: int,
    service_date: date,
    hospital_network_required: Optional[str],
    billed_amount_cents: int,
) -> dict:
    """
    Check whether a hospital is in the plan's required network.
    Returns {in_network: bool, copayment_cents: int, trigger: str|None}
    """
    if hospital_network_required == "OPEN":
        return {"in_network": True, "copayment_cents": 0, "trigger": None}

    network_types = await get_provider_network_types(
        db, provider_id, scheme_id, service_date
    )

    required_network_type = {
        "PRIME": "PRIME_HOSPITAL",
        "COMPACT": "COMPACT_HOSPITAL",
    }.get(hospital_network_required, "PRIME_HOSPITAL")

    in_network = required_network_type in network_types

    copayment_cents = 0
    trigger = None
    if not in_network:
        trigger = "NON_NETWORK_HOSPITAL"
        copayment_cents = await calculate_copayment(
            db, scheme_id, plan_option_id, trigger, billed_amount_cents
        )

    return {
        "in_network": in_network,
        "copayment_cents": copayment_cents,
        "trigger": trigger,
    }


async def check_gp_network(
    db: AsyncSession,
    provider_id: int,
    scheme_id: int,
    plan_option_id: int,
    plan_code: str,
    service_date: date,
    billed_amount_cents: int,
    non_network_visits_used: int = 0,
    non_network_visits_allowed: int = 2,
) -> dict:
    """
    Check whether a GP is in the plan's required network.
    Plans with gp_referral_required allow 2 non-network GP visits per family per year
    before the 40% co-payment kicks in.
    """
    # Determine the GP network type for this plan
    gp_network_map = {
        "MEDIPHILA": "GP_MEDIPHILA",
        "MEDIVALUE_PRIME": "GP_MEDIVALUE",
        "MEDIVALUE_COMPACT": "GP_MEDIVALUE",
        "MEDIPLUS_PRIME": "GP_MEDIPLUS",
        "MEDIPLUS_COMPACT": "GP_MEDIPLUS",
        "MEDICURVE": "GP_MEDICURVE",
    }
    gp_network_type = gp_network_map.get(plan_code)

    if not gp_network_type:
        return {"in_network": True, "copayment_cents": 0, "trigger": None}

    network_types = await get_provider_network_types(
        db, provider_id, scheme_id, service_date
    )
    in_network = gp_network_type in network_types

    copayment_cents = 0
    trigger = None
    if not in_network:
        if non_network_visits_used >= non_network_visits_allowed:
            trigger = "NON_NETWORK_GP_VISITS_EXCEEDED"
            copayment_cents = await calculate_copayment(
                db, scheme_id, plan_option_id, trigger, billed_amount_cents
            )
        # else: within the free 2-visit allowance, no co-payment

    return {
        "in_network": in_network,
        "copayment_cents": copayment_cents,
        "trigger": trigger,
        "visits_used": non_network_visits_used,
        "visits_allowed": non_network_visits_allowed,
    }


async def check_dsp_network(
    db: AsyncSession,
    provider_id: int,
    scheme_id: int,
    plan_option_id: int,
    benefit_category: str,
    service_date: date,
    billed_amount_cents: int,
) -> dict:
    """
    Check whether a provider is the required DSP for a given benefit category.
    Returns {in_network: bool, copayment_cents: int, trigger: str|None}
    """
    if benefit_category not in DSP_REQUIRED_CATEGORIES:
        return {"in_network": True, "copayment_cents": 0, "trigger": None}

    trigger = DSP_TRIGGER_MAP.get(benefit_category)
    if trigger is None:
        # No automatic co-payment rule — handled by clinical protocol
        return {"in_network": True, "copayment_cents": 0, "trigger": None}

    # Each benefit category maps to a specific DSP network type
    dsp_network_type_map = {
        "CHRONIC_MEDICINE": ["PHARMACY_CHRONIC_DSP", "PHARMACY_DIRECT"],
        "HIV_AIDS": ["HIV_DSP", "PHARMACY_DIRECT"],
        "CHRONIC_RENAL_DIALYSIS": ["DIALYSIS_DSP"],
        "ONCOLOGY": ["ONCOLOGY_ICON"],
        "ONCOLOGY_PET_SCAN": ["ONCOLOGY_ICON"],
    }
    required_types = dsp_network_type_map.get(benefit_category, [])

    network_types = await get_provider_network_types(
        db, provider_id, scheme_id, service_date
    )
    in_network = bool(set(required_types) & set(network_types))

    copayment_cents = 0
    if not in_network:
        copayment_cents = await calculate_copayment(
            db, scheme_id, plan_option_id, trigger, billed_amount_cents
        )

    return {
        "in_network": in_network,
        "copayment_cents": copayment_cents,
        "trigger": trigger,
    }
