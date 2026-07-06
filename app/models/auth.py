from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    registration_number = Column(String(100), unique=True, nullable=False)
    cms_accreditation_number = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="scheme")
    members = relationship("Member", back_populates="scheme")
    plan_options = relationship("PlanOption", back_populates="scheme")
    claims = relationship("Claim", back_populates="scheme")
    theme = relationship("SchemeTheme", back_populates="scheme", uselist=False)


class SchemeTheme(Base):
    """Stores per-scheme UI branding/theming configuration.
    Kept separate from the Scheme business entity intentionally."""
    __tablename__ = "scheme_themes"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), unique=True, nullable=False, index=True)
    palette = Column(String(50), nullable=False, default="sapphire")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    scheme = relationship("Scheme", back_populates="theme")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scheme = relationship("Scheme", back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
    scheme_memberships = relationship("UserSchemeMembership", back_populates="user")


class UserSchemeMembership(Base):
    """Maps users to the schemes they may access. Supports TPA users who work across multiple schemes."""
    __tablename__ = "user_scheme_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("user_id", "scheme_id", name="uq_user_scheme"),)

    user = relationship("User", back_populates="scheme_memberships")
    scheme = relationship("Scheme")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    # Enterprise extensions
    event_id = Column(String(36), nullable=True)        # UUID for cross-system correlation
    user_role = Column(String(50), nullable=True)       # role at time of action
    ip_address = Column(String(45), nullable=True)      # IPv4 or IPv6
    is_pmb_override = Column(Boolean, default=False)    # flag if action was a PMB override
    claim_rejection_code = Column(String(20), nullable=True)
    reason = Column(String(500), nullable=True)         # mandatory for status changes

    user = relationship("User", back_populates="audit_logs")
