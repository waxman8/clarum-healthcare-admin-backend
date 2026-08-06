import pytest
from datetime import datetime, timezone, timedelta
from app.models.auth import AuditLog, User, Scheme
from app.repositories.audit_log_repository import AuditLogRepository
from app.constants import AuditAction


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_scheme(db_session):
    # Setup
    scheme1 = Scheme(name="Scheme 1", code="S1", registration_number="REG1")
    scheme2 = Scheme(name="Scheme 2", code="S2", registration_number="REG2")
    db_session.add_all([scheme1, scheme2])
    await db_session.commit()

    log1 = AuditLog(scheme_id=scheme1.id, entity_type="MEMBER", action=AuditAction.CREATE)
    log2 = AuditLog(scheme_id=scheme2.id, entity_type="MEMBER", action=AuditAction.CREATE)
    db_session.add_all([log1, log2])
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute
    items, total = await repo.list(scheme_id=scheme1.id)

    # Assert
    assert total == 1
    assert items[0].id == log1.id


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_action(db_session):
    # Setup
    scheme = Scheme(name="Scheme", code="S", registration_number="REG")
    db_session.add(scheme)
    await db_session.commit()

    log1 = AuditLog(scheme_id=scheme.id, entity_type="MEMBER", action=AuditAction.CREATE)
    log2 = AuditLog(scheme_id=scheme.id, entity_type="MEMBER", action=AuditAction.UPDATE)
    db_session.add_all([log1, log2])
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute
    items, total = await repo.list(scheme_id=scheme.id, action=AuditAction.CREATE)

    # Assert
    assert total == 1
    assert items[0].action == AuditAction.CREATE


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_date_range(db_session):
    # Setup
    scheme = Scheme(name="Scheme", code="S", registration_number="REG")
    db_session.add(scheme)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    old_log = AuditLog(
        scheme_id=scheme.id, 
        entity_type="MEMBER", 
        action=AuditAction.CREATE,
        timestamp=now - timedelta(days=10)
    )
    new_log = AuditLog(
        scheme_id=scheme.id, 
        entity_type="MEMBER", 
        action=AuditAction.CREATE,
        timestamp=now
    )
    db_session.add_all([old_log, new_log])
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute
    items, total = await repo.list(
        scheme_id=scheme.id, 
        date_from=now - timedelta(days=1)
    )

    # Assert
    assert total == 1
    assert items[0].id == new_log.id


@pytest.mark.asyncio
async def test_get_audit_log_prevents_cross_scheme_access(db_session):
    # Setup
    scheme1 = Scheme(name="Scheme 1", code="S1", registration_number="REG1")
    scheme2 = Scheme(name="Scheme 2", code="S2", registration_number="REG2")
    db_session.add_all([scheme1, scheme2])
    await db_session.commit()

    log1 = AuditLog(scheme_id=scheme1.id, entity_type="MEMBER", action=AuditAction.CREATE)
    db_session.add(log1)
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute & Assert
    assert await repo.get(scheme_id=scheme1.id, audit_log_id=log1.id) is not None
    assert await repo.get(scheme_id=scheme2.id, audit_log_id=log1.id) is None


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_actor(db_session):
    # Setup
    scheme = Scheme(name="Scheme", code="S", registration_number="REG")
    db_session.add(scheme)
    await db_session.commit()

    user1 = User(email="u1@test.co.za", full_name="User 1", role="admin", hashed_password="pw")
    user2 = User(email="u2@test.co.za", full_name="User 2", role="admin", hashed_password="pw")
    db_session.add_all([user1, user2])
    await db_session.commit()

    log1 = AuditLog(scheme_id=scheme.id, entity_type="MEMBER", action=AuditAction.CREATE, user_id=user1.id)
    log2 = AuditLog(scheme_id=scheme.id, entity_type="MEMBER", action=AuditAction.CREATE, user_id=user2.id)
    db_session.add_all([log1, log2])
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute
    items, total = await repo.list(scheme_id=scheme.id, actor_id=user1.id)

    # Assert
    assert total == 1
    assert items[0].user_id == user1.id


@pytest.mark.asyncio
async def test_list_audit_logs_filters_by_entity_type(db_session):
    # Setup
    scheme = Scheme(name="Scheme", code="S", registration_number="REG")
    db_session.add(scheme)
    await db_session.commit()

    log1 = AuditLog(scheme_id=scheme.id, entity_type="MEMBER", action=AuditAction.CREATE)
    log2 = AuditLog(scheme_id=scheme.id, entity_type="CLAIM", action=AuditAction.CREATE)
    db_session.add_all([log1, log2])
    await db_session.commit()

    repo = AuditLogRepository(db_session)
    
    # Execute
    items, total = await repo.list(scheme_id=scheme.id, entity_type="MEMBER")

    # Assert
    assert total == 1
    assert items[0].entity_type == "MEMBER"
