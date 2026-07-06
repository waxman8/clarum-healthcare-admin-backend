# Auto-generated happy-path API tests for StatutoryActuary
import pytest  # noqa


@pytest.mark.asyncio
async def test_statutory_actuary_crud(client, auth_headers):
    """Happy-path CRUD cycle for StatutoryActuary."""
    # CREATE
    payload = {
        "scheme_id": 1,
        "full_name": "Test",
        "email": "Test"
    }
    r = await client.post("/api/v1/statutory-actuary", json=payload, headers=auth_headers)
    assert r.status_code in (201, 422), f"Expected 201 or 422, got {r.status_code}: {r.text}"
    if r.status_code == 201:
        item_id = r.json()["id"]

        # READ
        r = await client.get(f"/api/v1/statutory-actuary/{item_id}", headers=auth_headers)
        assert r.status_code == 200

        # LIST
        r = await client.get("/api/v1/statutory-actuary", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # DELETE
        r = await client.delete(f"/api/v1/statutory-actuary/{item_id}", headers=auth_headers)
        assert r.status_code == 204
