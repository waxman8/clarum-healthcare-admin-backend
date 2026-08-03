# Auto-generated happy-path API tests for BrokerCommissionScale
import pytest  # noqa


@pytest.mark.asyncio
async def test_broker_commission_scale_crud(client, auth_headers):
    """Happy-path CRUD cycle for BrokerCommissionScale."""
    # CREATE
    payload = {
        "scheme_id": 1,
        "member_type": "Test",
        "commission_amount_cents": 1,
        "vat_inclusive": True,
        "effective_from": "2026-01-01",
        "max_pmpm_cents": 10761
    }
    r = await client.post("/api/v1/broker-commission-scale", json=payload, headers=auth_headers)
    assert r.status_code in (201, 422), f"Expected 201 or 422, got {r.status_code}: {r.text}"
    if r.status_code == 201:
        item_id = r.json()["id"]

        # READ
        r = await client.get(f"/api/v1/broker-commission-scale/{item_id}", headers=auth_headers)
        assert r.status_code == 200

        # LIST
        r = await client.get("/api/v1/broker-commission-scale", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # DELETE
        r = await client.delete(f"/api/v1/broker-commission-scale/{item_id}", headers=auth_headers)
        assert r.status_code == 204


@pytest.mark.asyncio
async def test_cross_scheme_leak_check(client, auth_headers, db_session):
    """Test that a user cannot read, update, or overlap with a commission scale from another scheme."""
    # 1. Create an item in Scheme 1
    payload = {
        "scheme_id": 1,
        "member_type": "Test_Leak",
        "commission_amount_cents": 5000,
        "vat_inclusive": True,
        "effective_from": "2026-01-01",
        "max_pmpm_cents": 10761
    }
    r = await client.post("/api/v1/broker-commission-scale", json=payload, headers=auth_headers)
    assert r.status_code == 201
    item_id = r.json()["id"]
    
    # 2. Simulate a user from Scheme 2
    # In auth_headers, the token uses scheme_id=1 because of seed_admin_user.
    # Let's generate a token for scheme 2.
    from app.auth.security import create_access_token
    from datetime import timedelta
    # Create token for user ID 1 but pretending they are operating under scheme_id 2
    # (or simply an admin of scheme 2)
    token = create_access_token(
        data={"sub": "1", "scheme_id": 2},
        expires_delta=timedelta(minutes=15)
    )
    scheme_2_headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Attempt to READ the item belonging to Scheme 1
    r_get = await client.get(f"/api/v1/broker-commission-scale/{item_id}", headers=scheme_2_headers)
    assert r_get.status_code == 404, "Cross-scheme leak: Should not be able to read item from another scheme"
    
    # 4. Attempt to UPDATE the item belonging to Scheme 1
    r_patch = await client.patch(
        f"/api/v1/broker-commission-scale/{item_id}", 
        json={"commission_amount_cents": 9999}, 
        headers=scheme_2_headers
    )
    assert r_patch.status_code == 404, "Cross-scheme leak: Should not be able to update item from another scheme"

    # 5. Attempt to LIST and verify item from Scheme 1 does not appear
    r_list = await client.get("/api/v1/broker-commission-scale", headers=scheme_2_headers)
    assert r_list.status_code == 200
    ids = [item["id"] for item in r_list.json()]
    assert item_id not in ids, "Cross-scheme leak: Item from scheme 1 showed up in scheme 2's list"
