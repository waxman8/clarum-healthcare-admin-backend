import pytest
from httpx import AsyncClient
from app.models.auth import AuditLog, User, Scheme
from app.constants import Role, AuditAction


@pytest.mark.asyncio
async def test_get_audit_logs_requires_auth(client: AsyncClient):
    # 'client' is the fixture name from conftest.py
    response = await client.get("/api/v1/audit-log")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_audit_log_mutation_returns_405(client: AsyncClient, auth_headers):
    # Spec says all write endpoints should return 405
    response = await client.post("/api/v1/audit-log", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.put("/api/v1/audit-log/1", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.patch("/api/v1/audit-log/1", headers=auth_headers)
    assert response.status_code == 405
    
    response = await client.delete("/api/v1/audit-log/1", headers=auth_headers)
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
    response = await client.get("/api/v1/audit-log", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Assert: log from scheme 2 should not be present
    for item in data["items"]:
        assert item["id"] != log2.id

    # Execute: try to fetch scheme 2 log by ID
    response = await client.get(f"/api/v1/audit-log/{log2.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_audit_logs_pagination(client: AsyncClient, db_session, auth_headers):
    # Setup: current_user belongs to scheme 1
    # Create 30 logs for scheme 1
    for i in range(30):
        log = AuditLog(scheme_id=1, entity_type="MEMBER", action=AuditAction.CREATE)
        db_session.add(log)
    await db_session.commit()
    
    # Execute: fetch first page
    response = await client.get("/api/v1/audit-log?page=1&page_size=20", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 20
    assert data["total"] >= 30
    
    # Execute: fetch second page
    response = await client.get("/api/v1/audit-log?page=2&page_size=20", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 10


@pytest.mark.asyncio
async def test_get_audit_logs_date_range_validation(client: AsyncClient, auth_headers):
    from datetime import datetime, timedelta, timezone
    
    # Valid range (7 days)
    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=7)
    
    response = await client.get(
        "/api/v1/audit-log", 
        params={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat()
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    
    # Invalid range (91 days)
    date_from = date_to - timedelta(days=91)
    response = await client.get(
        "/api/v1/audit-log",
        params={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat()
        },
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "Date range span cannot exceed 90 days" in response.json()["detail"]

    # Invalid range (querying more than 90 days back without date_to)
    date_from = date_to - timedelta(days=91)
    response = await client.get(
        "/api/v1/audit-log",
        params={
            "date_from": date_from.isoformat()
        },
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "Date range span cannot exceed 90 days" in response.json()["detail"]
