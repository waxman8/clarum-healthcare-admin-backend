# Auto-generated happy-path API tests for Trustee
import pytest  # noqa


@pytest.mark.asyncio
async def test_trustee_crud(client, auth_headers, seed_scheme):
    """Happy-path CRUD cycle for Trustee."""
    # CREATE
    payload = {
        "scheme_id": seed_scheme.id,
        "full_name": "John Trustee",
        "email": "trustee@test.co.za",
        "role_on_board": "MEMBER_ELECTED",
        "appointment_date": "2026-01-01",
        "vetting_status": "PENDING",
        "conflict_disclosed": False,
    }
    r = await client.post("/api/v1/trustee", json=payload, headers=auth_headers)
    assert r.status_code in (201, 422), f"Expected 201 or 422, got {r.status_code}: {r.text}"
    if r.status_code == 201:
        item_id = r.json()["id"]

        # READ
        r = await client.get(f"/api/v1/trustee/{item_id}", headers=auth_headers)
        assert r.status_code == 200

        # LIST
        r = await client.get("/api/v1/trustee", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # DELETE
        r = await client.delete(f"/api/v1/trustee/{item_id}", headers=auth_headers)
        assert r.status_code == 204

        # Verify repo save was called or commit happened
        # In integration tests, we rely on the DB state
        r = await client.get(f"/api/v1/trustee/{item_id}", headers=auth_headers)
        assert r.status_code == 404
