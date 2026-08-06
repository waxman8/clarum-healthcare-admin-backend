import pytest
from app.constants import MemberStatus, Relationship


@pytest.mark.asyncio
async def test_nominee_bulk_sync_success(client, scheme_admin_headers, seed_member):
    """Test successful sync of nominees (50% + 50%)."""
    payload = [
        {
            "member_id": seed_member.id,
            "full_name": "Nominee One",
            "id_number": "1234567890123",
            "relationship": Relationship.SPOUSE,
            "allocation_pct": 50
        },
        {
            "member_id": seed_member.id,
            "full_name": "Nominee Two",
            "id_number": "9876543210987",
            "relationship": Relationship.CHILD,
            "allocation_pct": 50
        }
    ]
    r = await client.put(f"/api/v1/beneficiary-nomination/sync/{seed_member.id}", json=payload, headers=scheme_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert sum(n["allocation_pct"] for n in data) == 100


@pytest.mark.asyncio
async def test_nominee_sync_invalid_total(client, scheme_admin_headers, seed_member):
    """Test sync rejection when total allocation != 100."""
    payload = [
        {
            "member_id": seed_member.id,
            "full_name": "Nominee One",
            "id_number": "1234567890123",
            "relationship": Relationship.SPOUSE,
            "allocation_pct": 60
        },
        {
            "member_id": seed_member.id,
            "full_name": "Nominee Two",
            "id_number": "9876543210987",
            "relationship": Relationship.CHILD,
            "allocation_pct": 30
        }
    ]
    r = await client.put(f"/api/v1/beneficiary-nomination/sync/{seed_member.id}", json=payload, headers=scheme_admin_headers)
    assert r.status_code == 400
    assert "Total allocation must be exactly 100%" in r.json()["detail"]


@pytest.mark.asyncio
async def test_nominee_max_count(client, scheme_admin_headers, seed_member):
    """Test rejection of more than 4 nominees."""
    payload = [
        {
            "member_id": seed_member.id,
            "full_name": f"Nominee {i}",
            "id_number": f"{i}234567890123",
            "relationship": Relationship.OTHER,
            "allocation_pct": 20
        } for i in range(5)
    ]
    r = await client.put(f"/api/v1/beneficiary-nomination/sync/{seed_member.id}", json=payload, headers=scheme_admin_headers)
    assert r.status_code == 400
    assert "Maximum 4 nominees allowed" in r.json()["detail"]


@pytest.mark.asyncio
async def test_nominee_terminated_member(client, scheme_admin_headers, db_session, seed_member):
    """Test rejection of nominees for terminated members."""
    # Terminate member
    seed_member.status = MemberStatus.CANCELLED
    await db_session.commit()

    payload = [
        {
            "member_id": seed_member.id,
            "full_name": "Nominee One",
            "id_number": "1234567890123",
            "relationship": Relationship.SPOUSE,
            "allocation_pct": 100
        }
    ]
    r = await client.put(f"/api/v1/beneficiary-nomination/sync/{seed_member.id}", json=payload, headers=scheme_admin_headers)
    assert r.status_code == 400
    assert "Cannot manage nominees of a terminated member" in r.json()["detail"]


@pytest.mark.asyncio
async def test_nominee_cross_scheme_leak(client, scheme_admin_headers, seed_other_member):
    """Test that a scheme admin cannot see or edit nominees of another scheme."""
    # Try to sync for other scheme's member
    payload = []
    r = await client.put(f"/api/v1/beneficiary-nomination/sync/{seed_other_member.id}", json=payload, headers=scheme_admin_headers)
    # Should be 404 Member Not Found because of scheme filtering in service
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_nominee_role_access(client, seed_member):
    """Test role-based access control."""
    # No auth
    r = await client.get(f"/api/v1/beneficiary-nomination?member_id={seed_member.id}")
    assert r.status_code == 401
