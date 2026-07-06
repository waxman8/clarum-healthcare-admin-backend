"""Integration tests for the members endpoints."""
import pytest
from app.constants import MemberStatus


@pytest.mark.asyncio
async def test_create_member(client, auth_headers, seed_scheme, seed_plan):
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
    }
    resp = await client.post("/api/v1/members", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "John"
    assert data["status"] == MemberStatus.ACTIVE
    assert data["membership_number"].startswith("TEST-")


@pytest.mark.asyncio
async def test_list_members_scheme_scoped(client, auth_headers, seed_member):
    resp = await client.get("/api/v1/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [m["id"] for m in data["items"]]
    assert seed_member.id in ids


@pytest.mark.asyncio
async def test_get_member_by_id(client, auth_headers, seed_member):
    resp = await client.get(f"/api/v1/members/{seed_member.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == seed_member.id


@pytest.mark.asyncio
async def test_get_nonexistent_member_returns_404(client, auth_headers):
    resp = await client.get("/api/v1/members/999999", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_members(client, auth_headers, seed_member):
    resp = await client.get(
        "/api/v1/members",
        params={"search": seed_member.first_name},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()["items"]]
    assert seed_member.id in ids


@pytest.mark.asyncio
async def test_update_member_status(client, auth_headers, seed_member):
    resp = await client.post(
        f"/api/v1/members/{seed_member.id}/status",
        json={"status": "suspended", "reason": "Non-payment"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"
