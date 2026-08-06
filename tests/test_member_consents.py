import json

import pytest
from sqlalchemy import select

from app.models.auth import AuditLog
from app.models.members import MemberConsent


@pytest.mark.asyncio
async def test_get_member_consents_returns_all_purposes_unrecorded(client, auth_headers, seed_member):
    resp = await client.get(
        f"/api/v1/members/{seed_member.id}/consents",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["member_id"] == seed_member.id
    assert len(data["consents"]) == 6
    assert all(item["current"] is None for item in data["consents"])


@pytest.mark.asyncio
async def test_grant_consent(client, scheme_admin_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": True},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["consents"] if i["purpose"]["code"] == "MARKETING")
    assert item["current"]["consented"] is True
    assert item["current"]["withdrew_at"] is None


@pytest.mark.asyncio
async def test_withdraw_consent_without_reason_fails(client, scheme_admin_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": False},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_withdraw_consent_mutates_single_row(
    client, scheme_admin_headers, seed_member, db_session
):
    await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": True},
        headers=scheme_admin_headers,
    )
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": False, "reason": "Member requested opt-out"},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["consents"] if i["purpose"]["code"] == "MARKETING")
    assert item["current"]["consented"] is False
    assert item["current"]["withdrew_at"] is not None
    assert item["current"]["withdraw_reason"] == "Member requested opt-out"

    result = await db_session.execute(
        select(MemberConsent).where(
            MemberConsent.member_id == seed_member.id, MemberConsent.purpose == "MARKETING"
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].consented is False


@pytest.mark.asyncio
async def test_regrant_after_withdraw_reuses_same_row(client, scheme_admin_headers, seed_member, db_session):
    await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": True},
        headers=scheme_admin_headers,
    )
    await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": False, "reason": "opt-out"},
        headers=scheme_admin_headers,
    )
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": True},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["consents"] if i["purpose"]["code"] == "MARKETING")
    assert item["current"]["consented"] is True
    assert item["current"]["withdrew_at"] is None
    assert item["current"]["withdraw_reason"] is None

    result = await db_session.execute(
        select(MemberConsent).where(
            MemberConsent.member_id == seed_member.id, MemberConsent.purpose == "MARKETING"
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_invalid_purpose_rejected(client, scheme_admin_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "NOT_A_REAL_PURPOSE", "consented": True},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_claims_processor_cannot_record_consent(client, claims_processor_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MARKETING", "consented": True},
        headers=claims_processor_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_call_centre_agent_can_record_consent(client, call_centre_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "GENERAL", "consented": True},
        headers=call_centre_headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_cross_scheme_member_consents_are_hidden(client, auth_headers, seed_other_member):
    resp = await client.get(
        f"/api/v1/members/{seed_other_member.id}/consents",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_scheme_record_consent_is_hidden(client, auth_headers, seed_other_member):
    resp = await client.post(
        f"/api/v1/members/{seed_other_member.id}/consents",
        json={"purpose": "GENERAL", "consented": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_record_consent_writes_audit_log(client, scheme_admin_headers, seed_member, db_session):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "SHARE_WITH_ADMIN", "consented": True},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "member_consent")
    )
    audit_logs = audit_result.scalars().all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "grant"
    payload = json.loads(audit_logs[0].new_value)
    assert payload["purpose"] == "SHARE_WITH_ADMIN"
    assert payload["consented"] is True


@pytest.mark.asyncio
async def test_consent_audit_log_accumulates_across_actions_on_same_purpose(
    client, scheme_admin_headers, seed_member
):
    await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MEDICAL_HISTORY_ANALYTICS", "consented": True},
        headers=scheme_admin_headers,
    )
    await client.post(
        f"/api/v1/members/{seed_member.id}/consents",
        json={"purpose": "MEDICAL_HISTORY_ANALYTICS", "consented": False, "reason": "changed mind"},
        headers=scheme_admin_headers,
    )

    resp = await client.get(
        f"/api/v1/members/{seed_member.id}/consents/audit-log",
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert len(entries) == 2
    actions = {e["action"] for e in entries}
    assert actions == {"grant", "withdraw"}
    withdraw_entry = next(e for e in entries if e["action"] == "withdraw")
    assert withdraw_entry["reason"] == "changed mind"


@pytest.mark.asyncio
async def test_cross_scheme_consent_audit_log_is_hidden(client, auth_headers, seed_other_member):
    resp = await client.get(
        f"/api/v1/members/{seed_other_member.id}/consents/audit-log",
        headers=auth_headers,
    )
    assert resp.status_code == 404
