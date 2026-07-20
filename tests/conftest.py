"""
Pytest fixtures for integration tests.

All seed fixtures are session-scoped — data is created once and shared
across the entire test run. The in-memory SQLite engine is also session-scoped
so each test sees the same DB state.
"""
import asyncio
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.auth.security import get_password_hash
from app.constants import Role, MemberStatus


# ---------------------------------------------------------------------------
# Event loop — single loop for the whole test session
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop


# ---------------------------------------------------------------------------
# In-memory database  (one engine per session)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Function-scoped DB session."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client wired to the in-memory DB
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Minimal seed helpers  (all session-scoped — created once, shared by all tests)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def seed_scheme(db_session):
    from app.models.auth import Scheme
    scheme = Scheme(
        name="Test Scheme",
        code="TEST",
        registration_number="TEST-REG-001",
        is_active=True,
    )
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    return scheme


@pytest_asyncio.fixture(scope="function")
async def seed_plan(db_session, seed_scheme):
    from app.models.reference import PlanOption
    plan = PlanOption(
        scheme_id=seed_scheme.id,
        name="Test Plan",
        code="TEST-BASIC",
        monthly_premium=50000,
        is_active=True,
        hospital_network="OPEN",
        day_to_day_type="LIMIT",
        tariff_multiplier=100,
        benefit_year=2026,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture(scope="function")
async def seed_member(db_session, seed_scheme, seed_plan):
    from app.models.members import Member
    member = Member(
        scheme_id=seed_scheme.id,
        membership_number="TEST-2026-000001",
        id_number="8001015009087",
        first_name="Jane",
        surname="Doe",
        date_of_birth=date(1980, 1, 1),
        gender="F",
        plan_option_id=seed_plan.id,
        status=MemberStatus.ACTIVE,
        join_date=date(2026, 1, 1),
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member


@pytest_asyncio.fixture(scope="function")
async def seed_provider(db_session):
    from app.models.providers import Provider
    provider = Provider(
        practice_number="PR-TEST-001",
        discipline_code="GP",
        provider_type="gp",
        trading_name="Test GP Practice",
        is_active=True,
        is_dsp=False,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


@pytest_asyncio.fixture(scope="function")
async def seed_admin_user(db_session, seed_scheme):
    from app.models.auth import User
    user = User(
        email="admin@test.co.za",
        full_name="Test Admin",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.SUPER_ADMIN,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client, seed_admin_user):
    """Return Authorization headers for the admin user."""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.co.za", "password": "Test@1234"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def seed_scheme_admin_user(db_session, seed_scheme):
    from app.models.auth import User
    user = User(
        email="schemeadmin@test.co.za",
        full_name="Scheme Admin",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.SCHEME_ADMIN,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def scheme_admin_headers(client, seed_scheme_admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "schemeadmin@test.co.za", "password": "Test@1234"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def seed_call_centre_user(db_session, seed_scheme):
    from app.models.auth import User
    user = User(
        email="callcentre@test.co.za",
        full_name="Call Centre",
        hashed_password=get_password_hash("Test@1234"),
        role=Role.CALL_CENTRE_AGENT,
        scheme_id=seed_scheme.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def call_centre_headers(client, seed_call_centre_user):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "callcentre@test.co.za", "password": "Test@1234"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def seed_other_scheme(db_session):
    from app.models.auth import Scheme
    scheme = Scheme(
        name="Other Scheme",
        code="OTHR",
        registration_number="OTHR-REG-001",
        is_active=True,
    )
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    return scheme


@pytest_asyncio.fixture(scope="function")
async def seed_other_plan(db_session, seed_other_scheme):
    from app.models.reference import PlanOption
    plan = PlanOption(
        scheme_id=seed_other_scheme.id,
        name="Other Plan",
        code="OTHR-BASIC",
        monthly_premium=40000,
        is_active=True,
        hospital_network="OPEN",
        day_to_day_type="LIMIT",
        tariff_multiplier=100,
        benefit_year=2026,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture(scope="function")
async def seed_other_member(db_session, seed_other_scheme, seed_other_plan):
    from app.models.members import Member
    member = Member(
        scheme_id=seed_other_scheme.id,
        membership_number="OTHR-2026-000001",
        id_number="8101015009082",
        first_name="Other",
        surname="Member",
        date_of_birth=date(1981, 1, 1),
        gender="F",
        plan_option_id=seed_other_plan.id,
        status=MemberStatus.ACTIVE,
        join_date=date(2026, 1, 1),
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member
