from datetime import date
import pytest
from sqlalchemy import select

from app.constants import ClaimStatus, RecoveryStatus, RecoveryType, Role
from app.models.auth import AuditLog, Scheme, User
from app.models.claims import Claim
from app.auth.security import get_password_hash


@pytest.mark.asyncio
async def test_create_recovery_case(client, auth_headers, db_session):
    payload = {
        "recovery_type": RecoveryType.COB,
        "third_party_name": "Discovery Health",
        "third_party_reference": "REF-12345",
        "expected_cents": 100000,
    }
    resp = await client.post("/api/v1/recovery-cases", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["recovery_type"] == RecoveryType.COB
    assert data["third_party_name"] == "Discovery Health"
    assert data["status"] == RecoveryStatus.IDENTIFIED
    assert data["expected_cents"] == 100000
    assert data["recovered_cents"] == 0
    assert data["outstanding_cents"] == 100000
    case_id = data["id"]

    # Verify AuditLog created
    db_session.expire_all()
    res = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "recovery_case", AuditLog.entity_id == case_id, AuditLog.action == "create")
    )
    assert res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_link_claim_and_allocation_limits(client, auth_headers, db_session, seed_scheme, seed_member, seed_provider):
    # 1. Create a Recovery Case
    case_payload = {
        "recovery_type": RecoveryType.RAF,
        "third_party_name": "Road Accident Fund",
        "expected_cents": 50000,
    }
    case_resp = await client.post("/api/v1/recovery-cases", json=case_payload, headers=auth_headers)
    assert case_resp.status_code == 201
    case_id = case_resp.json()["id"]

    # 2. Seed a Claim
    claim = Claim(
        scheme_id=seed_scheme.id,
        member_id=seed_member.id,
        provider_id=seed_provider.id,
        claim_number="CLM-REC-001",
        date_of_service_from=date(2026, 1, 15),
        date_of_service_to=date(2026, 1, 15),
        date_received=date(2026, 1, 15),
        claim_type="day_to_day",
        status=ClaimStatus.APPROVED,
        total_billed=60000,
        total_approved=60000,
        recovered_cents=0,
    )
    db_session.add(claim)
    await db_session.commit()
    await db_session.refresh(claim)

    # 3. Link claim exceeding expected_cents -> 400
    link_exceed_expected = {"claim_id": claim.id, "allocation_cents": 60000}
    resp = await client.post(f"/api/v1/recovery-cases/{case_id}/claims", json=link_exceed_expected, headers=auth_headers)
    assert resp.status_code == 400
    assert "cannot exceed the expected recovery amount" in resp.json()["detail"]

    # 4. Link claim with valid allocation using friendly claim_number
    link_valid = {"claim_id": "CLM-REC-001", "allocation_cents": 40000}
    resp = await client.post(f"/api/v1/recovery-cases/{case_id}/claims", json=link_valid, headers=auth_headers)
    assert resp.status_code == 201
    link_data = resp.json()
    assert link_data["claim_id"] == claim.id
    assert link_data["claim_number"] == "CLM-REC-001"
    assert link_data["allocation_cents"] == 40000
    assert link_data["recovered_cents"] == 0

    # 5. Re-link same claim -> 400
    resp = await client.post(f"/api/v1/recovery-cases/{case_id}/claims", json=link_valid, headers=auth_headers)
    assert resp.status_code == 400
    assert "already linked" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_case_transitions_and_receipts(client, auth_headers, db_session, seed_scheme, seed_member, seed_provider):
    # 1. Create case expected R1000 (100000 cents)
    case_resp = await client.post(
        "/api/v1/recovery-cases",
        json={"recovery_type": RecoveryType.COIDA, "third_party_name": "Compensation Fund", "expected_cents": 100000},
        headers=auth_headers,
    )
    case_id = case_resp.json()["id"]

    # 2. Seed and link claim
    claim = Claim(
        scheme_id=seed_scheme.id,
        member_id=seed_member.id,
        provider_id=seed_provider.id,
        claim_number="CLM-REC-002",
        date_of_service_from=date(2026, 2, 1),
        date_of_service_to=date(2026, 2, 1),
        date_received=date(2026, 2, 1),
        claim_type="day_to_day",
        status=ClaimStatus.APPROVED,
        total_billed=100000,
        total_approved=100000,
        recovered_cents=0,
    )
    db_session.add(claim)
    await db_session.commit()
    await db_session.refresh(claim)

    await client.post(f"/api/v1/recovery-cases/{case_id}/claims", json={"claim_id": claim.id, "allocation_cents": 100000}, headers=auth_headers)

    # 3. Invalid transition: IDENTIFIED -> RECEIVED directly without receipt -> 400
    resp = await client.post(f"/api/v1/recovery-cases/{case_id}/transitions", json={"status": RecoveryStatus.RECEIVED}, headers=auth_headers)
    assert resp.status_code == 400

    # 4. Valid transition: IDENTIFIED -> SUBMITTED
    resp = await client.post(
        f"/api/v1/recovery-cases/{case_id}/transitions",
        json={"status": RecoveryStatus.SUBMITTED, "reason": "Submitted claim pack"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == RecoveryStatus.SUBMITTED

    # 5. Transition: SUBMITTED -> PARTIALLY_RECEIVED with receipt_cents=40000
    resp = await client.post(
        f"/api/v1/recovery-cases/{case_id}/transitions",
        json={
            "status": RecoveryStatus.PARTIALLY_RECEIVED,
            "receipt_cents": 40000,
            "received_on": "2026-03-01",
            "reason": "First partial settlement",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == RecoveryStatus.PARTIALLY_RECEIVED
    assert data["recovered_cents"] == 40000
    assert data["outstanding_cents"] == 60000
    assert len(data["receipts"]) == 1
    assert data["receipts"][0]["amount_cents"] == 40000

    # Verify claim recovered_cents was updated
    await db_session.refresh(claim)
    assert claim.recovered_cents == 40000

    # 6. Attempt RECEIVED when recovered != expected -> 400
    resp = await client.post(
        f"/api/v1/recovery-cases/{case_id}/transitions",
        json={"status": RecoveryStatus.RECEIVED, "receipt_cents": 10000},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "only be marked received when fully recovered" in resp.json()["detail"]

    # 7. Transition: PARTIALLY_RECEIVED -> RECEIVED with remaining 60000
    resp = await client.post(
        f"/api/v1/recovery-cases/{case_id}/transitions",
        json={
            "status": RecoveryStatus.RECEIVED,
            "receipt_cents": 60000,
            "received_on": "2026-03-15",
            "reason": "Final settlement received",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    final_data = resp.json()
    assert final_data["status"] == RecoveryStatus.RECEIVED
    assert final_data["recovered_cents"] == 100000
    assert final_data["outstanding_cents"] == 0
    assert len(final_data["receipts"]) == 2

    await db_session.refresh(claim)
    assert claim.recovered_cents == 100000


@pytest.mark.asyncio
async def test_cross_scheme_leak_prevention_recovery_cases(client, auth_headers, db_session):
    # Seed Scheme B & Case in Scheme B
    scheme_b = Scheme(name="Scheme B", code="SCHEMEB", registration_number="REG-SCH-B", is_active=True)
    db_session.add(scheme_b)
    await db_session.commit()
    await db_session.refresh(scheme_b)

    from app.models.recovery import RecoveryCase
    case_b = RecoveryCase(
        scheme_id=scheme_b.id,
        recovery_type=RecoveryType.COB,
        third_party_name="Other Insurer",
        expected_cents=50000,
        status=RecoveryStatus.IDENTIFIED,
    )
    db_session.add(case_b)
    await db_session.commit()
    await db_session.refresh(case_b)

    # Auth headers belong to Scheme A user
    resp = await client.get(f"/api/v1/recovery-cases/{case_b.id}", headers=auth_headers)
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/recovery-cases/{case_b.id}/transitions",
        json={"status": RecoveryStatus.SUBMITTED},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_role_gated_access_recovery_cases(client, db_session, seed_scheme):
    unauthorized_user = User(
        email="agent@test.co.za",
        full_name="Call Centre Agent",
        role=Role.CALL_CENTRE_AGENT,
        scheme_id=seed_scheme.id,
        hashed_password=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(unauthorized_user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "agent@test.co.za", "password": "Test@1234"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    agent_headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/recovery-cases", headers=agent_headers)
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/recovery-cases",
        json={"recovery_type": RecoveryType.COB, "third_party_name": "Test", "expected_cents": 1000},
        headers=agent_headers,
    )
    assert resp.status_code == 403
