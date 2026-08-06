"""
Tests for FEAT-0009: Login MFA (TOTP)

Covers all 10 cases from the plan §3.9.
"""
import json
import pytest
import pyotp
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.auth import User
from app.auth.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_mfa_user(db: AsyncSession, email: str = "mfa@test.co.za") -> User:
    """Create a fresh user with no MFA enabled."""
    user = User(
        email=email,
        full_name="MFA Test User",
        hashed_password=get_password_hash("TestPass@1234"),
        role="scheme_admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp


async def _get_auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    resp = await _login(client, email, password)
    assert resp.status_code == 200
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mfa_setup_returns_otpauth_url(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/setup returns an otpauth:// URL and a base32 secret."""
    await _create_mfa_user(db, "setup@test.co.za")
    headers = await _get_auth_headers(client, "setup@test.co.za", "TestPass@1234")

    resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["otpauth_url"].startswith("otpauth://totp/")
    assert "Clarum" in data["otpauth_url"]
    assert len(data["secret"]) >= 16  # base32 secret


@pytest.mark.asyncio
async def test_mfa_verify_activates_mfa_and_returns_recovery_codes(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/verify with a valid code enables MFA and returns 10 recovery codes."""
    await _create_mfa_user(db, "verify@test.co.za")
    headers = await _get_auth_headers(client, "verify@test.co.za", "TestPass@1234")

    # Get a fresh secret
    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]

    # Generate a valid TOTP code
    totp = pyotp.TOTP(secret)
    code = totp.now()

    resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": code},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert len(data["recovery_codes"]) == 10

    # Confirm DB state
    result = await db.execute(select(User).where(User.email == "verify@test.co.za"))
    user = result.scalar_one()
    assert user.totp_enabled is True
    assert user.totp_secret_enc is not None


@pytest.mark.asyncio
async def test_mfa_verify_wrong_code_rejected(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/verify with a wrong code returns 400."""
    await _create_mfa_user(db, "wrongcode@test.co.za")
    headers = await _get_auth_headers(client, "wrongcode@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]

    resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": "000000"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_with_mfa_enabled_returns_mfa_required(client: AsyncClient, db: AsyncSession):
    """POST /auth/login for a user with MFA enabled returns mfa_required + pre_auth_mfa_token."""
    await _create_mfa_user(db, "mfalogin@test.co.za")
    headers = await _get_auth_headers(client, "mfalogin@test.co.za", "TestPass@1234")

    # Enable MFA
    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )

    # Now login again — should get MFA required
    resp = await _login(client, "mfalogin@test.co.za", "TestPass@1234")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("mfa_required") is True
    assert "pre_auth_mfa_token" in data


@pytest.mark.asyncio
async def test_mfa_challenge_success_returns_jwt(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/challenge with a valid TOTP code returns access + refresh tokens."""
    await _create_mfa_user(db, "challenge@test.co.za")
    headers = await _get_auth_headers(client, "challenge@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )

    login_resp = await _login(client, "challenge@test.co.za", "TestPass@1234")
    pre_mfa_token = login_resp.json()["pre_auth_mfa_token"]

    challenge_resp = await client.post(
        "/api/v1/auth/mfa/challenge",
        json={"code": totp.now()},
        headers={"Authorization": f"Bearer {pre_mfa_token}"},
    )
    assert challenge_resp.status_code == 200
    data = challenge_resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_mfa_challenge_wrong_code_increments_fail_count(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/challenge with a wrong code increments totp_fail_count."""
    await _create_mfa_user(db, "failcount@test.co.za")
    headers = await _get_auth_headers(client, "failcount@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )

    login_resp = await _login(client, "failcount@test.co.za", "TestPass@1234")
    pre_mfa_token = login_resp.json()["pre_auth_mfa_token"]

    resp = await client.post(
        "/api/v1/auth/mfa/challenge",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {pre_mfa_token}"},
    )
    assert resp.status_code == 401

    result = await db.execute(select(User).where(User.email == "failcount@test.co.za"))
    user = result.scalar_one()
    assert user.totp_fail_count == 1


@pytest.mark.asyncio
async def test_mfa_challenge_lockout_after_5_failures(client: AsyncClient, db: AsyncSession):
    """5 consecutive wrong codes lock the account for 15 minutes."""
    await _create_mfa_user(db, "lockout@test.co.za")
    headers = await _get_auth_headers(client, "lockout@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )

    login_resp = await _login(client, "lockout@test.co.za", "TestPass@1234")
    pre_mfa_token = login_resp.json()["pre_auth_mfa_token"]

    for _ in range(5):
        await client.post(
            "/api/v1/auth/mfa/challenge",
            json={"code": "000000"},
            headers={"Authorization": f"Bearer {pre_mfa_token}"},
        )

    # 5th failure should lock; subsequent attempt returns 423
    resp = await client.post(
        "/api/v1/auth/mfa/challenge",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {pre_mfa_token}"},
    )
    assert resp.status_code == 423

    result = await db.execute(select(User).where(User.email == "lockout@test.co.za"))
    user = result.scalar_one()
    assert user.totp_lockout_until is not None


@pytest.mark.asyncio
async def test_mfa_challenge_recovery_code_works_once(client: AsyncClient, db: AsyncSession):
    """A recovery code can be used once; second use is rejected."""
    await _create_mfa_user(db, "recovery@test.co.za")
    headers = await _get_auth_headers(client, "recovery@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    verify_resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )
    recovery_codes = verify_resp.json()["recovery_codes"]
    recovery_code = recovery_codes[0]

    # First login — get pre_mfa_token
    login_resp = await _login(client, "recovery@test.co.za", "TestPass@1234")
    pre_mfa_token = login_resp.json()["pre_auth_mfa_token"]

    # Use recovery code — should succeed
    resp1 = await client.post(
        "/api/v1/auth/mfa/challenge",
        json={"code": recovery_code},
        headers={"Authorization": f"Bearer {pre_mfa_token}"},
    )
    assert resp1.status_code == 200

    # Login again to get a fresh pre_mfa_token
    login_resp2 = await _login(client, "recovery@test.co.za", "TestPass@1234")
    pre_mfa_token2 = login_resp2.json()["pre_auth_mfa_token"]

    # Use same recovery code again — should fail
    resp2 = await client.post(
        "/api/v1/auth/mfa/challenge",
        json={"code": recovery_code},
        headers={"Authorization": f"Bearer {pre_mfa_token2}"},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_mfa_disable_requires_password_and_totp(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/disable requires correct password + fresh TOTP."""
    await _create_mfa_user(db, "disable@test.co.za")
    headers = await _get_auth_headers(client, "disable@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )

    # Wrong password — should fail
    resp_bad = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "WrongPass@1234", "code": totp.now()},
        headers=headers,
    )
    assert resp_bad.status_code == 400

    # Correct password + valid TOTP — should succeed
    resp_ok = await client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "TestPass@1234", "code": totp.now()},
        headers=headers,
    )
    assert resp_ok.status_code == 200

    result = await db.execute(select(User).where(User.email == "disable@test.co.za"))
    user = result.scalar_one()
    assert user.totp_enabled is False
    assert user.totp_secret_enc is None


@pytest.mark.asyncio
async def test_mfa_regenerate_recovery_codes(client: AsyncClient, db: AsyncSession):
    """POST /auth/mfa/recovery-codes/regenerate returns 10 new codes."""
    await _create_mfa_user(db, "regen@test.co.za")
    headers = await _get_auth_headers(client, "regen@test.co.za", "TestPass@1234")

    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)
    verify_resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"secret": secret, "code": totp.now()},
        headers=headers,
    )
    original_codes = verify_resp.json()["recovery_codes"]

    regen_resp = await client.post(
        "/api/v1/auth/mfa/recovery-codes/regenerate",
        headers=headers,
    )
    assert regen_resp.status_code == 200
    new_codes = regen_resp.json()["recovery_codes"]
    assert len(new_codes) == 10
    # New codes should differ from original
    assert set(new_codes) != set(original_codes)
