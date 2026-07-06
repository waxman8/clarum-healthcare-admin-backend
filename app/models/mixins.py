# Reusable SQLAlchemy mixins — Phase 0 building block.
# New entities inherit MultiTenant + Auditable by default;
# reference data inherits neither (per BUILD_PLAN.md).

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, event


class MultiTenant:
    """Adds scheme_id for row-level scheme isolation.

    Convention: scheme_id is a plain Integer column — NO ForeignKey constraint.
    The service / auth layer enforces scoping via _effective_scheme_id().
    """
    scheme_id = Column(
        Integer, nullable=False, index=True,
    )  # logical FK -> schemes (service-layer enforced)


class Auditable:
    """Adds created/updated timestamps and created_by/updated_by user tracking."""
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by = Column(Integer, nullable=True)   # logical FK -> users
    updated_by = Column(Integer, nullable=True)   # logical FK -> users


class SoftDeletable:
    """Marks rows as deleted instead of removing them.

    Queries should filter on `is_deleted == False` (or use a repository helper).
    """
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)   # logical FK -> users


class StatusHistory:
    """Adds a status field with last-changed tracking.

    Entities needing a full status audit trail should write to an
    <Entity>StatusHistory table in the service layer.
    """
    status = Column(String(50), nullable=False, default="ACTIVE")
    status_changed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    status_changed_by = Column(Integer, nullable=True)  # logical FK -> users
    status_reason = Column(String(500), nullable=True)


class Documented:
    """Flags that an entity can have file attachments.

    The actual attachments live in a separate `documents` table with a
    polymorphic (entity_type + entity_id) reference. This mixin just adds
    a convenience note/description field on the parent.
    """
    document_notes = Column(Text, nullable=True)
