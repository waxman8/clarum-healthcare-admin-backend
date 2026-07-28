import json

import pytest
from sqlalchemy import select

from app.constants import CommunicationCategory, CommunicationChannel
from app.integrations.mocks import MockMessagingGateway
from app.integrations.registry import bind, reset
from app.integrations.contracts import MessagingGateway
from app.models.auth import AuditLog
from app.models.members import MemberCommunicationPreference
from app.schemas.members import MemberCommunicationPreferenceUpdateItem
from app.services.communications_service import CommunicationsService
from app.services.member_communication_preference_service import MemberCommunicationPreferenceService
from app.repositories.member_communication_preference_repository import MemberCommunicationPreferenceRepository


@pytest.mark.asyncio
async def test_create_member_seeds_default_communication_preferences(
    client, auth_headers, seed_scheme, seed_plan, db_session
):
    payload = {
        "scheme_id": seed_scheme.id,
        "id_number": "9001015009086",
        "first_name": "John",
        "surname": "Smith",
        "date_of_birth": "1990-01-01",
        "gender": "M",
        "plan_option_id": seed_plan.id,
        "join_date": "2026-01-01",
        "email": "john@test.co.za",
        "cell_number": "0821234567",
        "status": "active",
    }
    resp = await client.post("/api/v1/members", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    member_id = resp.json()["id"]

    result = await db_session.execute(
        select(MemberCommunicationPreference).where(MemberCommunicationPreference.member_id == member_id)
    )
    prefs = result.scalars().all()
    assert len(prefs) == 9
    assert all(pref.is_opted_in for pref in prefs)


@pytest.mark.asyncio
async def test_get_member_communication_preferences_returns_matrix(client, auth_headers, seed_member):
    resp = await client.get(
        f"/api/v1/members/{seed_member.id}/communication-preferences",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["member_id"] == seed_member.id
    assert len(data["preferences"]) == 9
    combos = {(row["channel"], row["category"]) for row in data["preferences"]}
    assert len(combos) == 9


@pytest.mark.asyncio
async def test_update_member_communication_preferences_persists_and_audits(
    client, scheme_admin_headers, seed_member
):
    payload = {
        "preferences": [
            {
                "channel": CommunicationChannel.SMS,
                "category": CommunicationCategory.GENERAL,
                "is_opted_in": False,
            }
        ]
    }
    resp = await client.put(
        f"/api/v1/members/{seed_member.id}/communication-preferences",
        json=payload,
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    pref = next(
        row for row in resp.json()["preferences"]
        if row["channel"] == CommunicationChannel.SMS and row["category"] == CommunicationCategory.GENERAL
    )
    assert pref["is_opted_in"] is False


@pytest.mark.asyncio
async def test_non_admin_cannot_update_member_communication_preferences(
    client, call_centre_headers, seed_member
):
    payload = {
        "preferences": [
            {
                "channel": CommunicationChannel.EMAIL,
                "category": CommunicationCategory.BILLING,
                "is_opted_in": False,
            }
        ]
    }
    resp = await client.put(
        f"/api/v1/members/{seed_member.id}/communication-preferences",
        json=payload,
        headers=call_centre_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_service_update_member_communication_preferences_writes_audit_log(
    db_session, seed_member, seed_scheme_admin_user
):
    repo = MemberCommunicationPreferenceRepository(db_session)
    service = MemberCommunicationPreferenceService(db_session, repo)

    prefs = await service.update_preferences(
        seed_member,
        [
            MemberCommunicationPreferenceUpdateItem(
                channel=CommunicationChannel.SMS,
                category=CommunicationCategory.GENERAL,
                is_opted_in=False,
            )
        ],
        seed_scheme_admin_user,
    )
    await db_session.commit()

    assert any(
        pref.channel == CommunicationChannel.SMS and
        pref.category == CommunicationCategory.GENERAL and
        pref.is_opted_in is False
        for pref in prefs
    )

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "member_communication_preference")
    )
    audit_logs = audit_result.scalars().all()
    assert len(audit_logs) >= 1
    audit_payload = json.loads(audit_logs[0].new_value)
    assert audit_payload["channel"] == CommunicationChannel.SMS
    assert audit_payload["category"] == CommunicationCategory.GENERAL
    assert audit_payload["is_opted_in"] is False


@pytest.mark.asyncio
async def test_cross_scheme_member_communication_preferences_are_hidden(
    client, auth_headers, seed_other_member
):
    resp = await client.get(
        f"/api/v1/members/{seed_other_member.id}/communication-preferences",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_sms_suppressed_when_member_opted_out(db_session, seed_member):
    reset()
    mock_gateway = MockMessagingGateway()
    bind(MessagingGateway, mock_gateway)

    pref = MemberCommunicationPreference(
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        channel=CommunicationChannel.SMS,
        category=CommunicationCategory.GENERAL,
        is_opted_in=False,
    )
    db_session.add(pref)
    await db_session.commit()

    service = CommunicationsService(db_session)
    result = await service.send_sms(seed_member.id, CommunicationCategory.GENERAL, "hello")

    assert result.outcome == "SUPPRESSED"
    assert mock_gateway.sms_log == []

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "suppressed_send")
    )
    audit = audit_result.scalar_one()
    assert "hello" not in (audit.new_value or "")


@pytest.mark.asyncio
async def test_send_sms_calls_gateway_when_member_opted_in(db_session, seed_member):
    reset()
    mock_gateway = MockMessagingGateway()
    bind(MessagingGateway, mock_gateway)

    service = CommunicationsService(db_session)
    result = await service.send_sms(seed_member.id, CommunicationCategory.GENERAL, "hello")

    assert result.outcome == "SENT"
    assert len(mock_gateway.sms_log) == 1


@pytest.mark.asyncio
async def test_send_email_suppressed_when_member_opted_out(db_session, seed_member):
    reset()
    mock_gateway = MockMessagingGateway()
    bind(MessagingGateway, mock_gateway)

    pref = MemberCommunicationPreference(
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        channel=CommunicationChannel.EMAIL,
        category=CommunicationCategory.BILLING,
        is_opted_in=False,
    )
    db_session.add(pref)
    await db_session.commit()

    service = CommunicationsService(db_session)
    result = await service.send_email(
        seed_member.id,
        CommunicationCategory.BILLING,
        "john@test.co.za",
        "Billing Notice",
        "<p>body</p>",
        "body",
    )

    assert result.outcome == "SUPPRESSED"
    assert mock_gateway.email_log == []

    audit_result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "suppressed_send")
    )
    audit = audit_result.scalar_one()
    assert "Billing Notice" not in (audit.new_value or "")
    assert "<p>body</p>" not in (audit.new_value or "")
    assert "body" not in (audit.new_value or "")


@pytest.mark.asyncio
async def test_send_email_calls_gateway_when_member_opted_in(db_session, seed_member):
    reset()
    mock_gateway = MockMessagingGateway()
    bind(MessagingGateway, mock_gateway)

    service = CommunicationsService(db_session)
    result = await service.send_email(
        seed_member.id,
        CommunicationCategory.BILLING,
        "john@test.co.za",
        "Billing Notice",
        "<p>body</p>",
        "body",
    )

    assert result.outcome == "SENT"
    assert len(mock_gateway.email_log) == 1
