"""Integration tests for the adjudication pipeline (rules engine)."""
from datetime import date

import pytest

from app.constants import MemberStatus, PipelineStatus, BenefitBucket, DayToDayType


@pytest.mark.asyncio
async def test_rules_engine_active_member_passes(db_session, seed_member, seed_provider):
    from app.services.rules_engine import run_rules_engine

    lines = [{"tariff_code": "0190", "billed_amount": 45600, "icd10_code": None}]
    results = await run_rules_engine(
        db=db_session,
        member_id=seed_member.id,
        provider_id=seed_provider.id,
        date_of_service_from=date(2026, 3, 1),
        claim_lines=lines,
    )
    member_rule = next(r for r in results if "Member Eligibility" in r.rule)
    assert member_rule.status == PipelineStatus.PASS


@pytest.mark.asyncio
async def test_rules_engine_service_before_join_fails(db_session, seed_member, seed_provider):
    from app.services.rules_engine import run_rules_engine

    lines = [{"tariff_code": "0190", "billed_amount": 45600, "icd10_code": None}]
    # DOS before join_date (2026-01-01)
    results = await run_rules_engine(
        db=db_session,
        member_id=seed_member.id,
        provider_id=seed_provider.id,
        date_of_service_from=date(2025, 12, 1),
        claim_lines=lines,
    )
    member_rule = next(r for r in results if "Member Eligibility" in r.rule)
    assert member_rule.status == PipelineStatus.FAIL


@pytest.mark.asyncio
async def test_rules_engine_inactive_member_fails(db_session, seed_scheme, seed_plan, seed_provider):
    """Creates a separate suspended member — does not mutate the shared seed_member."""
    from app.models.members import Member
    from app.services.rules_engine import run_rules_engine

    suspended = Member(
        scheme_id=seed_scheme.id,
        membership_number="TEST-2026-SUSPENDED",
        id_number="7501015009088",
        first_name="Inactive",
        surname="User",
        date_of_birth=date(1975, 1, 1),
        gender="M",
        plan_option_id=seed_plan.id,
        status="suspended",
        join_date=date(2026, 1, 1),
    )
    db_session.add(suspended)
    await db_session.commit()

    lines = [{"tariff_code": "0190", "billed_amount": 45600, "icd10_code": None}]
    results = await run_rules_engine(
        db=db_session,
        member_id=suspended.id,
        provider_id=seed_provider.id,
        date_of_service_from=date(2026, 3, 1),
        claim_lines=lines,
    )
    member_rule = next(r for r in results if "Member Eligibility" in r.rule)
    assert member_rule.status == PipelineStatus.FAIL


@pytest.mark.asyncio
async def test_rules_engine_inactive_provider_fails(db_session, seed_member):
    """Creates a separate inactive provider — does not mutate the shared seed_provider."""
    from app.models.providers import Provider
    from app.services.rules_engine import run_rules_engine

    inactive_prov = Provider(
        practice_number="PR-TEST-INACTIVE",
        discipline_code="GP",
        provider_type="gp",
        trading_name="Closed Practice",
        is_active=False,
        is_dsp=False,
    )
    db_session.add(inactive_prov)
    await db_session.commit()

    lines = [{"tariff_code": "0190", "billed_amount": 45600, "icd10_code": None}]
    results = await run_rules_engine(
        db=db_session,
        member_id=seed_member.id,
        provider_id=inactive_prov.id,
        date_of_service_from=date(2026, 3, 1),
        claim_lines=lines,
    )
    provider_rule = next(r for r in results if "Provider" in r.rule)
    assert provider_rule.status == PipelineStatus.FAIL


@pytest.mark.asyncio
async def test_benefit_bucket_routing_limit_plan(seed_plan):
    """day_to_day_type=LIMIT should route day-to-day claims to DAY_TO_DAY bucket."""
    from app.services.rules_engine import _determine_benefit_bucket, LineAdjudicationState

    assert seed_plan.day_to_day_type == DayToDayType.LIMIT

    class FakeClaim:
        auth_number = None
        claim_type = "outpatient"

    class FakeCtx:
        plan_option = seed_plan
        claim = FakeClaim()
        icd10_map = {}
        chronic_registrations = []

    state = LineAdjudicationState(
        line_id=1,
        tariff_code="0190",
        icd10_code=None,
        nappi_code_id=None,
        quantity=1,
        billed_amount=45600,
        is_pmb=False,
    )
    bucket = _determine_benefit_bucket(state, FakeCtx())
    assert bucket == BenefitBucket.DAY_TO_DAY
