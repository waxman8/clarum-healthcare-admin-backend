"""Shared helper for writing to the generic AuditLog table.

Used by every router that mutates a user-facing entity, so audit rows are
written consistently and are all visible through the generic
GET /api/v1/audit-log endpoint (app/routers/audit_log.py).
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AuditLog


def log_audit(
    db: AsyncSession,
    entity_type: str,
    entity_id: Optional[int],
    action: str,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
    scheme_id: Optional[int] = None,
    entity_label: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Add an AuditLog row to the session. Caller is responsible for committing."""
    db.add(AuditLog(
        user_id=user_id,
        user_role=user_role,
        scheme_id=scheme_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        action=action,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    ))
