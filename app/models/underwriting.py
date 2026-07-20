from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Text, JSON, ForeignKey
from sqlalchemy.types import Numeric
from sqlalchemy.orm import relationship as sa_relationship
from datetime import datetime, timezone
from app.database import Base


class UnderwritingDecision(Base):
    __tablename__ = "underwriting_decisions"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, nullable=False, index=True)
    member_id = Column(Integer, nullable=False, index=True)
    decision_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=False)

    # Outcome type: "approved" | "conditionally_approved" | "denied" | "referred"
    decision = Column(String(30), nullable=False)
    # Lifecycle: "active" | "superseded" | "referred" | "denied"
    status = Column(String(20), nullable=False, default="active")

    # Prior cover
    has_prior_cover = Column(Boolean, default=False)
    prior_cover_years = Column(Numeric(5, 2), nullable=True)
    prior_cover_break_days = Column(Integer, nullable=True)
    prior_cover_proof_type = Column(String(50), nullable=True)   # "certificate" | "affidavit" | ...
    prior_cover_schemes_json = Column(JSON, nullable=True)        # [{name, years, gap_days}]

    # General waiting period
    general_wp_months = Column(Integer, nullable=True)           # 0 = waived, 3 = standard
    general_wp_end_date = Column(Date, nullable=True)

    # Late-joiner (MSA Regulation 8)
    is_late_joiner = Column(Boolean, default=False)
    late_joiner_uncovered_years = Column(Integer, nullable=True)
    late_joiner_penalty_pct = Column(Integer, default=0)         # 0 / 5 / 25 / 50 / 75

    # Contribution (frozen at decision time — cents)
    base_monthly_contribution = Column(Integer, nullable=True)
    total_monthly_contribution = Column(Integer, nullable=True)

    # Audit
    created_by = Column(Integer, nullable=False)                 # user_id
    notes = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    modified_date = Column(DateTime(timezone=True), nullable=True)
    modified_user = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Phase 2 hook — NULL = manual entry
    engine_version = Column(String(20), nullable=True)
    rules_triggered_json = Column(JSON, nullable=True)

    condition_exclusions = sa_relationship(
        "MemberConditionExclusion",
        back_populates="decision",
        cascade="all, delete-orphan",
    )


class MemberConditionExclusion(Base):
    __tablename__ = "member_condition_exclusions"

    id = Column(Integer, primary_key=True, index=True)
    underwriting_decision_id = Column(Integer, ForeignKey("underwriting_decisions.id"), nullable=False, index=True)
    member_id = Column(Integer, nullable=False, index=True)
    scheme_id = Column(Integer, nullable=False)

    icd10_code = Column(String(20), nullable=False)
    condition_name = Column(String(200), nullable=True)
    is_pmb = Column(Boolean, default=False)
    exclusion_start_date = Column(Date, nullable=False)
    exclusion_end_date = Column(Date, nullable=False)  # typically start + 12 months

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    decision = sa_relationship("UnderwritingDecision", back_populates="condition_exclusions")


class EnrollmentQuestionnaire(Base):
    __tablename__ = "enrollment_questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, nullable=False, index=True)
    scheme_id = Column(Integer, nullable=False)

    # Gate 1 — reason for joining
    # "new_entrant" | "dependant_becoming_principal" | "transfer" | "other"
    join_reason = Column(String(50), nullable=False)

    # Prior cover
    has_prior_cover = Column(Boolean, default=False)
    prior_cover_years = Column(Numeric(5, 2), nullable=True)
    prior_cover_break_days = Column(Integer, nullable=True)
    prior_cover_proof_type = Column(String(50), nullable=True)
    prior_cover_schemes_json = Column(JSON, nullable=True)

    # Late-joiner inputs
    is_late_joiner = Column(Boolean, default=False)
    late_joiner_uncovered_years = Column(Integer, nullable=True)

    # Pre-existing conditions declared by applicant
    conditions_declared = Column(Boolean, default=False)
    declared_conditions_json = Column(JSON, nullable=True)  # [{icd10_code, condition_name}]

    # Audit
    completed_by = Column(Integer, nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    modified_date = Column(DateTime(timezone=True), nullable=True)
    modified_user = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Outcome — set after engine evaluation
    status = Column(String(20), nullable=False, default="pending")  # "pending" | "processed"
    underwriting_decision_id = Column(Integer, nullable=True)
    engine_outcome = Column(String(30), nullable=True)
