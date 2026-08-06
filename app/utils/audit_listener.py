import json
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.models.auth import AuditLog, User
from app.models.mixins import MultiTenant, Auditable
from app.utils.audit_context import get_current_user_context
from app.constants import AuditAction
from app.auth.dependencies import _effective_scheme_id

def json_serializable(obj):
    """Recursive helper to make SQLAlchemy objects JSON serializable."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    return str(obj)

def get_model_changes(instance):
    """Return a dict of changed attributes and their values."""
    state = instance._sa_instance_state
    changes = {}
    for attr in state.manager.mapper.column_attrs:
        key = attr.key
        history = state.get_history(key, True)
        if history.has_changes():
            changes[key] = history.added[0] if history.added else None
    return changes

def get_model_dict(instance):
    """Return a dict of all attributes and their values, excluding internal state."""
    return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}

def setup_audit_listeners():
    @event.listens_for(Session, "after_flush")
    def receive_after_flush(session, flush_context):
        current_user = get_current_user_context()
        if not current_user:
            return

        scheme_id = _effective_scheme_id(current_user)
        
        # Use connection.execute to avoid Session flush recursion
        conn = session.connection()

        # Capture inserts
        for instance in session.new:
            if isinstance(instance, (AuditLog,)):
                continue
            
            if hasattr(instance, '__tablename__'):
                conn.execute(
                    AuditLog.__table__.insert().values(
                        user_id=current_user.id,
                        scheme_id=scheme_id or getattr(instance, 'scheme_id', None),
                        entity_type=instance.__tablename__,
                        entity_id=getattr(instance, 'id', None),
                        action=AuditAction.CREATE,
                        new_value=json.dumps(get_model_dict(instance), default=json_serializable),
                        user_role=current_user.role,
                        timestamp=datetime.now(timezone.utc)
                    )
                )

        # Capture updates
        for instance in session.dirty:
            if isinstance(instance, (AuditLog,)):
                continue
                
            if hasattr(instance, '__tablename__'):
                state = instance._sa_instance_state
                old_values = {}
                new_values = {}
                
                for attr in state.manager.mapper.column_attrs:
                    history = state.get_history(attr.key, True)
                    if history.has_changes():
                        old_values[attr.key] = history.deleted[0] if history.deleted else None
                        new_values[attr.key] = history.added[0] if history.added else None
                
                if old_values or new_values:
                    conn.execute(
                        AuditLog.__table__.insert().values(
                            user_id=current_user.id,
                            scheme_id=scheme_id or getattr(instance, 'scheme_id', None),
                            entity_type=instance.__tablename__,
                            entity_id=getattr(instance, 'id', None),
                            action=AuditAction.UPDATE,
                            old_value=json.dumps(old_values, default=json_serializable),
                            new_value=json.dumps(new_values, default=json_serializable),
                            user_role=current_user.role,
                            timestamp=datetime.now(timezone.utc)
                        )
                    )

        # Capture deletes
        for instance in session.deleted:
            if isinstance(instance, (AuditLog,)):
                continue
                
            if hasattr(instance, '__tablename__'):
                conn.execute(
                    AuditLog.__table__.insert().values(
                        user_id=current_user.id,
                        scheme_id=scheme_id or getattr(instance, 'scheme_id', None),
                        entity_type=instance.__tablename__,
                        entity_id=getattr(instance, 'id', None),
                        action=AuditAction.DELETE,
                        old_value=json.dumps(get_model_dict(instance), default=json_serializable),
                        user_role=current_user.role,
                        timestamp=datetime.now(timezone.utc)
                    )
                )
