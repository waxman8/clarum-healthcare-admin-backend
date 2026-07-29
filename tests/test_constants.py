"""Smoke tests to verify constants are consistent with model defaults."""
import pytest
from app.constants import (
    Role, MemberStatus, ClaimStatus, AuthStatus,
    ChronicStatus, DisputeStatus, BenefitBucket,
    MemberType, PipelineStatus, DayToDayType, HospitalNetwork,
)


def test_role_all_contains_all_roles():
    assert Role.SUPER_ADMIN in Role.ALL
    assert Role.SCHEME_ADMIN in Role.ALL
    assert Role.CLAIMS_PROCESSOR in Role.ALL
    assert Role.AUTHORISATION_OFFICER in Role.ALL
    assert Role.FINANCE_OFFICER in Role.ALL
    assert Role.CALL_CENTRE_AGENT in Role.ALL
    assert Role.INFO_OFFICER in Role.ALL
    assert len(Role.ALL) == 7


def test_role_permission_groups_are_subsets():
    for role in Role.CAN_ADJUDICATE:
        assert role in Role.ALL
    for role in Role.CAN_APPROVE_AUTH:
        assert role in Role.ALL
    for role in Role.CAN_DECIDE_CHRONIC:
        assert role in Role.ALL
    for role in Role.CAN_RESOLVE_DISPUTE:
        assert role in Role.ALL


def test_dispute_open_statuses():
    assert DisputeStatus.OPEN in DisputeStatus.OPEN_STATUSES
    assert DisputeStatus.UNDER_REVIEW in DisputeStatus.OPEN_STATUSES
    assert DisputeStatus.UPHELD not in DisputeStatus.OPEN_STATUSES


def test_dispute_valid_resolutions_excludes_open():
    for s in DisputeStatus.OPEN_STATUSES:
        assert s not in DisputeStatus.VALID_RESOLUTIONS


def test_benefit_bucket_not_decremented():
    assert BenefitBucket.PMB_RISK in BenefitBucket.NOT_DECREMENTED
    assert BenefitBucket.MEMBER_LIABILITY in BenefitBucket.NOT_DECREMENTED
    assert BenefitBucket.HOSPITAL not in BenefitBucket.NOT_DECREMENTED


def test_pipeline_active_statuses():
    assert PipelineStatus.PENDING in PipelineStatus.ACTIVE
    assert PipelineStatus.FLAG in PipelineStatus.ACTIVE
    assert PipelineStatus.PASS not in PipelineStatus.ACTIVE
    assert PipelineStatus.FAIL not in PipelineStatus.ACTIVE
