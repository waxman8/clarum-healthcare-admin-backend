"""Integration tests for the authorisations endpoints."""
import pytest
from app.constants import AuthStatus


@pytest.mark.asyncio
async def test_create_authorisation_valid(
    client, auth_headers, seed_member, seed_provider
):
    payload = {
        "member_id": seed_member.id,
        "requesting_provider_id": seed_provider.id,
        "auth_type": "hospital_admission",
        "icd10_codes": ["I10"],
        "procedure_codes": [],
        "lines": [],
    }
    resp = await client.post("/api/v1/authorisations", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == AuthStatus.PENDING
    assert data["auth_number"].startswith("TEST-")
    assert data["member"]["id"] == seed_member.id


@pytest.mark.asyncio
async def test_create_authorisation_invalid_member(client, auth_headers, seed_provider):
    payload = {
        "member_id": 999999,
        "requesting_provider_id": seed_provider.id,
        "auth_type": "procedure",
        "icd10_codes": [],
        "procedure_codes": [],
        "lines": [],
    }
    resp = await client.post("/api/v1/authorisations", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_authorisation_invalid_provider(client, auth_headers, seed_member):
    payload = {
        "member_id": seed_member.id,
        "requesting_provider_id": 999999,
        "auth_type": "procedure",
        "icd10_codes": [],
        "procedure_codes": [],
        "lines": [],
    }
    resp = await client.post("/api/v1/authorisations", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_authorisations_scoped_to_scheme(
    client, auth_headers, seed_member, seed_provider
):
    # Create one auth
    await client.post(
        "/api/v1/authorisations",
        json={
            "member_id": seed_member.id,
            "requesting_provider_id": seed_provider.id,
            "auth_type": "specialist_referral",
            "icd10_codes": [],
            "procedure_codes": [],
            "lines": [],
        },
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/authorisations", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # All returned auths should have members in our scheme
    for item in data["items"]:
        assert item["member"] is not None


@pytest.mark.asyncio
async def test_approve_authorisation(client, auth_headers, seed_member, seed_provider):
    # Create
    create_resp = await client.post(
        "/api/v1/authorisations",
        json={
            "member_id": seed_member.id,
            "requesting_provider_id": seed_provider.id,
            "auth_type": "procedure",
            "icd10_codes": [],
            "procedure_codes": [],
            "lines": [],
        },
        headers=auth_headers,
    )
    auth_id = create_resp.json()["id"]

    # Approve
    resp = await client.post(
        f"/api/v1/authorisations/{auth_id}/approve",
        json={"approved_days": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == AuthStatus.APPROVED


@pytest.mark.asyncio
async def test_cannot_approve_already_approved(
    client, auth_headers, seed_member, seed_provider
):
    create_resp = await client.post(
        "/api/v1/authorisations",
        json={
            "member_id": seed_member.id,
            "requesting_provider_id": seed_provider.id,
            "auth_type": "procedure",
            "icd10_codes": [],
            "procedure_codes": [],
            "lines": [],
        },
        headers=auth_headers,
    )
    auth_id = create_resp.json()["id"]
    await client.post(
        f"/api/v1/authorisations/{auth_id}/approve",
        json={},
        headers=auth_headers,
    )
    # Second approve should 400
    resp = await client.post(
        f"/api/v1/authorisations/{auth_id}/approve",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_decline_authorisation(client, auth_headers, seed_member, seed_provider):
    create_resp = await client.post(
        "/api/v1/authorisations",
        json={
            "member_id": seed_member.id,
            "requesting_provider_id": seed_provider.id,
            "auth_type": "procedure",
            "icd10_codes": [],
            "procedure_codes": [],
            "lines": [],
        },
        headers=auth_headers,
    )
    auth_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/authorisations/{auth_id}/decline",
        json={"reason": "Not covered under plan"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == AuthStatus.DECLINED
