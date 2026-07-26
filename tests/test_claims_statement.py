import json
from datetime import date

import pytest
from sqlalchemy import select

from app.auth.security import create_access_token, get_password_hash
from app.constants import Role
from app.models.auth import AuditLog, User
from app.models.claims import Claim, ClaimLine
from app.models.members import Dependant
from app.services.claims_statement_service import build_claims_statement_payload, _build_claims_statement_html


async def _seed_claim(
    db_session,
    *,
    claim_number: str,
    member_id: int,
    scheme_id: int,
    provider_id: int,
    service_date: date,
    billed_cents: int,
    approved_cents: int,
    member_liability_cents: int,
    dependant_id: int | None = None,
):
    claim = Claim(
        claim_number=claim_number,
        scheme_id=scheme_id,
        member_id=member_id,
        dependant_id=dependant_id,
        provider_id=provider_id,
        date_of_service_from=service_date,
        date_of_service_to=service_date,
        date_received=service_date,
        claim_type="outpatient",
        status="approved",
        total_billed=billed_cents,
        total_approved=approved_cents,
        total_member_liability=member_liability_cents,
        total_scheme_liability=approved_cents,
    )
    db_session.add(claim)
    await db_session.flush()

    line = ClaimLine(
        claim_id=claim.id,
        tariff_code="0190",
        icd10_code="J11.1",
        quantity=1,
        billed_amount=billed_cents,
        approved_amount=approved_cents,
        member_liability=member_liability_cents,
    )
    db_session.add(line)
    await db_session.commit()
    await db_session.refresh(claim)
    return claim


@pytest.mark.asyncio
async def test_claims_statement_payload_grouping_and_totals(db_session, seed_member, seed_provider):
    dependant = Dependant(
        member_id=seed_member.id,
        dependant_relationship="child",
        id_number="1201015009084",
        first_name="Tiny",
        surname="Doe",
        date_of_birth=date(2012, 1, 1),
        gender="F",
        status="active",
        dependant_code="01",
    )
    db_session.add(dependant)
    await db_session.commit()
    await db_session.refresh(dependant)

    await _seed_claim(
        db_session,
        claim_number="CLM-TEST-0001",
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        provider_id=seed_provider.id,
        service_date=date(2026, 2, 5),
        billed_cents=10000,
        approved_cents=8000,
        member_liability_cents=2000,
    )
    await _seed_claim(
        db_session,
        claim_number="CLM-TEST-0002",
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        provider_id=seed_provider.id,
        service_date=date(2026, 3, 10),
        billed_cents=30000,
        approved_cents=25000,
        member_liability_cents=5000,
        dependant_id=dependant.id,
    )

    member = seed_member
    member.scheme = seed_member.scheme

    payload = await build_claims_statement_payload(
        db=db_session,
        member=member,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 12, 31),
    )

    assert len(payload["sections"]) == 2
    assert payload["sections"][0]["title"] == "Principal Member"
    assert payload["sections"][1]["title"].startswith("Dependant:")
    assert payload["sections"][0]["rows"][0]["date_of_service"] == "2026-02-05"
    assert payload["grand_totals"]["billed"] == 40000
    assert payload["grand_totals"]["approved"] == 33000
    assert payload["grand_totals"]["member_liability"] == 7000


@pytest.mark.asyncio
async def test_claims_statement_12_month_20_claims_totals_correct(db_session, seed_member, seed_provider):
    total_billed = 0
    total_approved = 0
    total_member_liability = 0

    for i in range(20):
        billed = 10000 + (i * 100)
        approved = 7000 + (i * 80)
        liability = billed - approved
        service_month = (i % 12) + 1
        service_day = (i % 27) + 1

        await _seed_claim(
            db_session,
            claim_number=f"CLM-TEST-{3000 + i}",
            member_id=seed_member.id,
            scheme_id=seed_member.scheme_id,
            provider_id=seed_provider.id,
            service_date=date(2026, service_month, service_day),
            billed_cents=billed,
            approved_cents=approved,
            member_liability_cents=liability,
        )

        total_billed += billed
        total_approved += approved
        total_member_liability += liability

    member = seed_member
    member.scheme = seed_member.scheme
    payload = await build_claims_statement_payload(
        db=db_session,
        member=member,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 12, 31),
    )

    assert payload["claim_count"] == 20
    assert payload["grand_totals"]["billed"] == total_billed
    assert payload["grand_totals"]["approved"] == total_approved
    assert payload["grand_totals"]["member_liability"] == total_member_liability


@pytest.mark.asyncio
async def test_download_member_claims_statement_pdf_defaults_and_audit(
    client,
    db_session,
    seed_scheme_admin_user,
    seed_member,
    seed_provider,
):
    await _seed_claim(
        db_session,
        claim_number="CLM-TEST-0101",
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        provider_id=seed_provider.id,
        service_date=date.today(),
        billed_cents=12000,
        approved_cents=10000,
        member_liability_cents=2000,
    )

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": seed_scheme_admin_user.email, "password": "Test@1234"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/api/v1/members/{seed_member.id}/claims-statement.pdf", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "attachment; filename=\"claims-statement-" in resp.headers.get("content-disposition", "")
    assert resp.content.startswith(b"%PDF")

    audit_result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "member_claims_statement", AuditLog.entity_id == seed_member.id)
        .order_by(AuditLog.id.desc())
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None
    data = json.loads(audit.new_value)
    assert data["from"] == date(date.today().year, 1, 1).isoformat()
    assert data["to"] == date.today().isoformat()
    assert data["scope"] == "staff"


@pytest.mark.asyncio
async def test_download_member_claims_statement_rejects_unauthorised_role(
    client,
    db_session,
    seed_scheme,
    seed_member,
):
    finance_user = User(
        email="finance@test.co.za",
        full_name="Finance Officer",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.FINANCE_OFFICER,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(finance_user)
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": finance_user.email, "password": "Test@1234"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/api/v1/members/{seed_member.id}/claims-statement.pdf", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_claims_statement_empty_period_includes_no_claims_message(
    client,
    db_session,
    seed_scheme_admin_user,
    seed_member,
):
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": seed_scheme_admin_user.email, "password": "Test@1234"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"/api/v1/members/{seed_member.id}/claims-statement.pdf",
        params={"from": "2024-01-01", "to": "2024-01-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")

    member = seed_member
    member.scheme = seed_member.scheme
    payload = await build_claims_statement_payload(
        db=db_session,
        member=member,
        period_from=date(2024, 1, 1),
        period_to=date(2024, 1, 31),
    )
    html = _build_claims_statement_html(member, payload)
    assert "No claims in period." in html


@pytest.mark.asyncio
async def test_download_member_claims_statement_blocks_cross_scheme(
    client,
    scheme_admin_headers,
    seed_other_member,
):
    resp = await client.get(
        f"/api/v1/members/{seed_other_member.id}/claims-statement.pdf",
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_portal_claims_statement_uses_own_member_record(
    client,
    db_session,
    seed_scheme,
    seed_member,
    seed_provider,
):
    seed_member.email = "member.portal@test.co.za"
    await db_session.commit()

    await _seed_claim(
        db_session,
        claim_number="CLM-TEST-0201",
        member_id=seed_member.id,
        scheme_id=seed_member.scheme_id,
        provider_id=seed_provider.id,
        service_date=date.today(),
        billed_cents=5000,
        approved_cents=4000,
        member_liability_cents=1000,
    )

    portal_user = User(
        email=seed_member.email,
        full_name="Portal Member",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.CALL_CENTRE_AGENT,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(portal_user)
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": portal_user.email, "password": "Test@1234"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/portal/members/me/claims-statement.pdf", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")

    audit_result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "member_claims_statement", AuditLog.entity_id == seed_member.id)
        .order_by(AuditLog.id.desc())
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None
    data = json.loads(audit.new_value)
    assert data["scope"] == "portal_self"


@pytest.mark.asyncio
async def test_portal_claims_statement_blocks_cross_scheme_via_token_member_id(
    client,
    seed_scheme,
    seed_other_member,
    seed_admin_user,
):
    token = create_access_token(
        {
            "sub": str(seed_admin_user.id),
            "scheme_id": seed_scheme.id,
            "member_id": seed_other_member.id,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/portal/members/me/claims-statement.pdf", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_portal_claims_statement_refuses_another_member_id_same_scheme(
    client,
    db_session,
    seed_scheme,
    seed_plan,
):
    own_member = User(
        email="selfportal@test.co.za",
        full_name="Self Portal",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.CALL_CENTRE_AGENT,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(own_member)

    from app.models.members import Member
    own_member_record = Member(
        scheme_id=seed_scheme.id,
        membership_number="TEST-2026-009901",
        id_number="8301015009087",
        first_name="Self",
        surname="Member",
        date_of_birth=date(1983, 1, 1),
        gender="F",
        email="selfportal@test.co.za",
        plan_option_id=seed_plan.id,
        status="active",
        join_date=date(2026, 1, 1),
    )
    other_member_record = Member(
        scheme_id=seed_scheme.id,
        membership_number="TEST-2026-009902",
        id_number="8401015009081",
        first_name="Other",
        surname="Member",
        date_of_birth=date(1984, 1, 1),
        gender="M",
        email="othermember@test.co.za",
        plan_option_id=seed_plan.id,
        status="active",
        join_date=date(2026, 1, 1),
    )
    db_session.add(own_member_record)
    db_session.add(other_member_record)
    await db_session.commit()
    await db_session.refresh(own_member)
    await db_session.refresh(other_member_record)

    token = create_access_token(
        {
            "sub": str(own_member.id),
            "scheme_id": seed_scheme.id,
            "member_id": other_member_record.id,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/portal/members/me/claims-statement.pdf", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_claims_statement_rejects_invalid_period(client, scheme_admin_headers, seed_member):
    resp = await client.get(
        f"/api/v1/members/{seed_member.id}/claims-statement.pdf",
        params={"from": "2026-12-31", "to": "2026-01-01"},
        headers=scheme_admin_headers,
    )
    assert resp.status_code == 400
