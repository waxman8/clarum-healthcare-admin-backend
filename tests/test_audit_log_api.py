import pytest
from httpx import AsyncClient
from app.models.auth import AuditLog, User, Scheme
from app.constants import Role, AuditAction


@pytest.mark.asyncio
async def test_get_audit_logs_requires_auth(client: AsyncClient):
    # 'client' is the fixture name from conftest.py
    response = await client.get("/audit-log")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_mutation_returns_405(client: AsyncClient, auth_headers):
    # Spec says all write endpoints should return 405
    response = await client.post("/audit-log", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.put("/audit-log/1", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.patch("/audit-log/1", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.delete("/audit-log/1", headers=auth_headers)
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_audit_log_api_isolation(client: AsyncClient, db_session, auth_headers):
    # Setup: current_user (from auth_headers) belongs to scheme 1 (seed_scheme)
    # Create log for scheme 2
    scheme2 = Scheme(name="Scheme 2", code="S2", registration_number="REG2")
    db_session.add(scheme2)
    await db_session.commit()
    
    log2 = AuditLog(scheme_id=scheme2.id, entity_type="MEMBER", action=AuditAction.CREATE)
    db_session.add(log2)
    await db_session.commit()
    
    # Execute: fetch logs (should be filtered to current user's scheme)
    response = await client.get("/audit-log", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Assert: log from scheme 2 should not be present
    for item in data["items"]:
        assert item["id"] != log2.id

    # Execute: try to fetch scheme 2 log by ID
    response = await client.get(f"/audit-log/{log2.id}", headers=auth_headers)
    assert response.status_code == 404
