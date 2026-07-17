import pytest
from app.models.auth import User, Scheme
from app.constants import Role, UserStatus
from app.integrations.registry import get as get_integration
from app.integrations.contracts import MessagingGateway


@pytest.mark.asyncio
async def test_users_api_crud_cycle(client, auth_headers):
    # 1. Clear Mock email log
    gateway = get_integration(MessagingGateway)
    gateway.email_log.clear()

    # 2. CREATE user
    create_payload = {
        "email": "new.user@test.co.za",
        "full_name": "New Portal User",
        "role": Role.SCHEME_ADMIN,
    }
    resp = await client.post("/api/v1/users", json=create_payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == "new.user@test.co.za"
    assert data["full_name"] == "New Portal User"
    assert data["role"] == Role.SCHEME_ADMIN
    assert data["is_active"] is True
    assert data["status"] == "active"
    assert data["must_reset_password"] is True
    user_id = data["id"]

    # Assert welcome email was captured
    assert len(gateway.email_log) == 1
    to, subject, html, text = gateway.email_log[0]
    assert to == "new.user@test.co.za"
    assert "Welcome" in subject
    assert "Clarum@" in text

    # 3. GET user
    resp = await client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Portal User"

    # 4. LIST users
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    list_data = resp.json()
    assert "items" in list_data
    assert list_data["total"] >= 1
    emails = [u["email"] for u in list_data["items"]]
    assert "new.user@test.co.za" in emails

    # 5. UPDATE user (inline edit of roles)
    update_payload = {
        "role": Role.CALL_CENTRE_AGENT,
        "full_name": "Updated Portal User",
    }
    resp = await client.patch(f"/api/v1/users/{user_id}", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == Role.CALL_CENTRE_AGENT
    assert resp.json()["full_name"] == "Updated Portal User"

    # 6. FORCE password reset
    gateway.email_log.clear()
    resp = await client.post(f"/api/v1/users/{user_id}/reset-password", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password reset email sent successfully"

    # Assert password reset email was captured
    assert len(gateway.email_log) == 1
    to, subject, html, text = gateway.email_log[0]
    assert to == "new.user@test.co.za"
    assert "Reset" in subject
    assert "Clarum@" in text

    # 7. DEACTIVATE user (toggling is_active=False via update)
    deactivate_payload = {
        "is_active": False
    }
    resp = await client.patch(f"/api/v1/users/{user_id}", json=deactivate_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert resp.json()["status"] == "deactivated"


@pytest.mark.asyncio
async def test_self_deactivation_guard(client, auth_headers):
    # Fetch current user ID from the response of whoami or similar, or list users to find admin@test.co.za
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    users = resp.json()["items"]
    admin_user = next(u for u in users if u["email"] == "admin@test.co.za")
    admin_id = admin_user["id"]

    # Try to deactivate self
    payload = {"is_active": False}
    resp = await client.patch(f"/api/v1/users/{admin_id}", json=payload, headers=auth_headers)
    assert resp.status_code == 400
    assert "Cannot deactivate yourself" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_scheme_leak_prevention(client, auth_headers, db_session):
    # Seed Scheme B
    scheme_b = Scheme(
        name="Scheme B",
        code="SCHEMEB",
        registration_number="TEST-REG-002",
        is_active=True,
    )
    db_session.add(scheme_b)
    await db_session.commit()
    await db_session.refresh(scheme_b)

    # Seed User in Scheme B
    from app.auth.security import get_password_hash
    user_b = User(
        email="user.b@schemeb.co.za",
        full_name="User B",
        role=Role.SCHEME_ADMIN,
        scheme_id=scheme_b.id,
        hashed_password=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(user_b)
    await db_session.commit()
    await db_session.refresh(user_b)

    # Try to fetch Scheme B user with Super Admin of Scheme A auth_headers (which is bound to scheme_id=1)
    resp = await client.get(f"/api/v1/users/{user_b.id}", headers=auth_headers)
    assert resp.status_code == 404

    # Try to update Scheme B user
    payload = {"full_name": "Leaked Update"}
    resp = await client.patch(f"/api/v1/users/{user_b.id}", json=payload, headers=auth_headers)
    assert resp.status_code == 404

    # Try to force password reset on Scheme B user
    resp = await client.post(f"/api/v1/users/{user_b.id}/reset-password", headers=auth_headers)
    assert resp.status_code == 404
