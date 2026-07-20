from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import relationship as sa_relationship
from datetime import datetime, timezone
from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    membership_number = Column(String(50), unique=True, nullable=False, index=True)
    id_number = Column(String(13), nullable=False, index=True)  # use "PASSPORT" if non-SA citizen
    passport_number = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)
    email = Column(String(255), nullable=True)
    cell_number = Column(String(20), nullable=True)
    physical_address = Column(Text, nullable=True)  # JSON: {line1, suburb, city, province, postal_code}
    plan_option_id = Column(Integer, ForeignKey("plan_options.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    join_date = Column(Date, nullable=False)
    termination_date = Column(Date, nullable=True)
    termination_reason = Column(String(200), nullable=True)
    # Underwriting fields — denormalised fast-lookup (authoritative source is UnderwritingDecision)
    waiting_period_end_date = Column(Date, nullable=True)
    late_joiner_penalty_pct = Column(Integer, default=0)  # 0 / 5 / 25 / 50 / 75
    popia_consent_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    modified_date = Column(DateTime(timezone=True), nullable=True)  # set explicitly by write endpoints, for audit trail
    modified_user = Column(Integer, ForeignKey("users.id"), nullable=True)

    scheme = sa_relationship("Scheme", back_populates="members")
    plan_option = sa_relationship("PlanOption", back_populates="members")
    dependants = sa_relationship("Dependant", back_populates="member")
    status_history = sa_relationship("MemberStatusHistory", back_populates="member")
    claims = sa_relationship("Claim", back_populates="member")
    authorisations = sa_relationship("Authorisation", back_populates="member")
    benefit_balances = sa_relationship("BenefitBalance", back_populates="member")
    savings_account = sa_relationship("SavingsAccount", back_populates="member", uselist=False)
    chronic_registrations = sa_relationship("ChronicRegistration", back_populates="member")
    disputes = sa_relationship("Dispute", back_populates="member")
    modified_by_user = sa_relationship("User", foreign_keys=[modified_user])


class Dependant(Base):
    __tablename__ = "dependants"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    dependant_relationship = Column("relationship", String(50), nullable=False)
    # Values: spouse | life_partner | child | student | adult_dependant | disabled_dependant
    id_number = Column(String(13), nullable=True)
    first_name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    dependant_code = Column(String(10), nullable=False)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    modified_date = Column(DateTime(timezone=True), nullable=True)
    modified_user = Column(Integer, ForeignKey("users.id"), nullable=True)

    member = sa_relationship("Member", back_populates="dependants")


class BenefitLimit(Base):
    __tablename__ = "benefit_limits"

    id = Column(Integer, primary_key=True, index=True)
    plan_option_id = Column(Integer, ForeignKey("plan_options.id"), nullable=False)
    benefit_category = Column(String(100), nullable=False)
    limit_type = Column(String(50), nullable=False)
    limit_value = Column(Integer, nullable=False)  # cents or visits
    applied_value = Column(Integer, nullable=False, default=0)
    benefit_year = Column(Integer, nullable=False)

    plan_option = sa_relationship("PlanOption", back_populates="benefit_limits")


class MemberStatusHistory(Base):
    __tablename__ = "member_status_history"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reason = Column(String(500), nullable=True)

    member = sa_relationship("Member", back_populates="status_history")
    changed_by_user = sa_relationship("User")
