import pytest
from app.models.auth import User, Scheme, AuditLog
from app.constants import Role, UserStatus, AuditAction
from app.integrations.registry import get as get_integration
from app.integrations.contracts import MessagingGateway
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from sqlalchemy import select


@pytest.mark.asyncio
async def test_users_api_crud_cycle(client, auth_headers, db_session):
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

    # Verify 'create' AuditLog entry was written
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action == AuditAction.CREATE)
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert "new.user@test.co.za" in audit.new_value

    # 3. GET user
    resp = await client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Portal User"

    # 4. LIST users (without filters)
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    list_data = resp.json()
    assert "items" in list_data
    assert list_data["total"] >= 1
    emails = [u["email"] for u in list_data["items"]]
    assert "new.user@test.co.za" in emails

    # 5. LIST users (with filters: search, role, status)
    # Search by email (positive)
    resp = await client.get("/api/v1/users?search=new.user", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["email"] == "new.user@test.co.za"

    # Search by name (positive)
    resp = await client.get("/api/v1/users?search=Portal", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Search (negative)
    resp = await client.get("/api/v1/users?search=nonexistent-query", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # Filter by role (positive)
    resp = await client.get(f"/api/v1/users?role={Role.SCHEME_ADMIN}", headers=auth_headers)
    assert resp.status_code == 200
    assert any(u["email"] == "new.user@test.co.za" for u in resp.json()["items"])

    # Filter by role (negative)
    resp = await client.get(f"/api/v1/users?role={Role.CLAIMS_PROCESSOR}", headers=auth_headers)
    assert resp.status_code == 200
    assert not any(u["email"] == "new.user@test.co.za" for u in resp.json()["items"])

    # Filter by status (positive - active)
    resp = await client.get("/api/v1/users?status=active", headers=auth_headers)
    assert resp.status_code == 200
    assert any(u["email"] == "new.user@test.co.za" for u in resp.json()["items"])

    # Filter by status (negative - deactivated)
    resp = await client.get("/api/v1/users?status=deactivated", headers=auth_headers)
    assert resp.status_code == 200
    assert not any(u["email"] == "new.user@test.co.za" for u in resp.json()["items"])

    # 6. UPDATE user (inline edit of roles, name)
    update_payload = {
        "role": Role.CALL_CENTRE_AGENT,
        "full_name": "Updated Portal User",
    }
    resp = await client.patch(f"/api/v1/users/{user_id}", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == Role.CALL_CENTRE_AGENT
    assert resp.json()["full_name"] == "Updated Portal User"

    # Verify 'role_change' and 'name_change' AuditLogs
    result_role = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action == AuditAction.ROLE_CHANGE)
    )
    assert result_role.scalar_one_or_none() is not None

    result_name = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action == AuditAction.NAME_CHANGE)
    )
    assert result_name.scalar_one_or_none() is not None

    # 7. FORCE password reset
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

    # Verify 'reset' AuditLog
    result_reset = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action == AuditAction.RESET)
    )
    assert result_reset.scalar_one_or_none() is not None

    # 8. DEACTIVATE user (toggling is_active=False via update)
    deactivate_payload = {
        "is_active": False
    }
    resp = await client.patch(f"/api/v1/users/{user_id}", json=deactivate_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert resp.json()["status"] == "deactivated"

    # Verify 'deactivate' AuditLog
    result_deact = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action == AuditAction.DEACTIVATE)
    )
    assert result_deact.scalar_one_or_none() is not None


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
async def test_list_users_paginates_without_changing_total(client, auth_headers):
    for email in ("page.one@test.co.za", "page.two@test.co.za"):
        resp = await client.post(
            "/api/v1/users",
            json={"email": email, "full_name": email, "role": Role.SCHEME_ADMIN},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text

    first_page = await client.get("/api/v1/users?skip=0&limit=1", headers=auth_headers)
    second_page = await client.get("/api/v1/users?skip=1&limit=1", headers=auth_headers)

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert second_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 1
    assert len(second_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]


@pytest.mark.asyncio
async def test_deactivate_user_service_handles_missing_and_already_inactive_users(
    db_session, seed_admin_user
):
    service = UserService(UserRepository(db_session), db_session)
    target_user = User(
        email="deactivate.target@test.co.za",
        full_name="Deactivate Target",
        role=Role.SCHEME_ADMIN,
        scheme_id=seed_admin_user.scheme_id,
        hashed_password="unused",
        is_active=True,
    )
    db_session.add(target_user)
    await db_session.commit()
    await db_session.refresh(target_user)

    assert await service.deactivate_user(9999, seed_admin_user) is False
    assert await service.deactivate_user(target_user.id, seed_admin_user) is True
    assert target_user.is_active is False
    assert await service.deactivate_user(target_user.id, seed_admin_user) is True

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
            AuditLog.action == AuditAction.DEACTIVATE,
        )
    )
    assert result.scalars().all()


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


@pytest.mark.asyncio
async def test_role_gated_access_prevention(client, db_session, seed_scheme):
    # Seed a non-Super-Admin user (e.g., Scheme Admin or Claims Processor)
    from app.auth.security import get_password_hash
    non_admin_user = User(
        email="scheme.admin@test.co.za",
        full_name="Scheme Admin User",
        role=Role.SCHEME_ADMIN,
        scheme_id=seed_scheme.id,
        hashed_password=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(non_admin_user)
    await db_session.commit()
    await db_session.refresh(non_admin_user)

    # Log in as the non-Super-Admin user
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "scheme.admin@test.co.za", "password": "Test@1234"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    non_admin_headers = {"Authorization": f"Bearer {token}"}

    # Verify they get 403 Forbidden on Users API endpoints
    resp = await client.get("/api/v1/users", headers=non_admin_headers)
    assert resp.status_code == 403

    resp = await client.post("/api/v1/users", json={"email": "hacker@test.co.za", "full_name": "Hack", "role": Role.SCHEME_ADMIN}, headers=non_admin_headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/users/1", headers=non_admin_headers)
    assert resp.status_code == 403

    resp = await client.patch("/api/v1/users/1", json={"full_name": "Hack"}, headers=non_admin_headers)
    assert resp.status_code == 403

    resp = await client.post("/api/v1/users/1/reset-password", headers=non_admin_headers)
    assert resp.status_code == 403
