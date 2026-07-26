from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class DisciplineCode(Base):
    """BHF standard discipline/specialty codes used across all schemes."""
    __tablename__ = "discipline_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)
    # MEDICAL | ALLIED | DENTAL | PHARMACY | FACILITY | OTHER
    is_active = Column(Boolean, default=True)


class ICD10Code(Base):
    __tablename__ = "icd10_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    is_pmb = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    # Enterprise extensions
    is_cdl = Column(Boolean, default=False)           # Chronic Disease List condition
    cdl_condition_name = Column(String(200), nullable=True)  # e.g. HYPERTENSION, ASTHMA
    gender_restriction = Column(String(10), nullable=True)   # M | F | NULL = both
    is_billable = Column(Boolean, default=True)


class TariffCode(Base):
    __tablename__ = "tariff_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    nhrpl_rate = Column(Integer, nullable=False)  # cents
    discipline_code = Column(String(10), nullable=True)  # kept for backward compat
    is_active = Column(Boolean, default=True)
    # Enterprise extensions
    tariff_list = Column(String(30), nullable=True)    # NHRPL | DENTAL | OPTOMETRY | PHARMACY | PATHOLOGY
    discipline_codes = Column(Text, nullable=True)     # JSON array for multi-discipline tariffs
    requires_auth = Column(Boolean, default=False)     # pre-authorisation required
    effective_year = Column(Integer, nullable=True)


class RejectionCode(Base):
    __tablename__ = "rejection_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    description = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False)


class ConsentPurpose(Base):
    """POPIA consent purposes — enum-seeded reference table."""
    __tablename__ = "consent_purposes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)


class PlanOption(Base):
    __tablename__ = "plan_options"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(20), nullable=False)
    monthly_premium = Column(Integer, nullable=False)  # cents
    is_active = Column(Boolean, default=True)
    # Enterprise extensions — drive adjudication routing (read from DB, never hardcoded)
    hospital_network = Column(String(20), nullable=True)       # OPEN | PRIME | COMPACT
    day_to_day_type = Column(String(20), nullable=True)        # LIMIT | SAVINGS | NONE
    care_coordination_required = Column(Boolean, default=False)
    gp_referral_required = Column(Boolean, default=False)
    benefit_year = Column(Integer, nullable=True)
    tariff_multiplier = Column(Integer, nullable=False, default=100)
    # 100 = pay at NHRPL; 200 = pay at 200% NHRPL (MST in-hospital for some plans)

    scheme = relationship("Scheme", back_populates="plan_options")
    members = relationship("Member", back_populates="plan_option")
    benefit_limits = relationship("BenefitLimit", back_populates="plan_option")
    contribution_rates = relationship("ContributionRate", back_populates="plan_option")
    copayment_rules = relationship("CopaymentRule", back_populates="plan_option")
    formulary_entries = relationship("Formulary", back_populates="plan_option")
