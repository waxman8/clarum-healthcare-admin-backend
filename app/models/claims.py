from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_number = Column(String(50), unique=True, nullable=False, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    dependant_id = Column(Integer, ForeignKey("dependants.id"), nullable=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    auth_number = Column(String(50), nullable=True)
    date_of_service_from = Column(Date, nullable=False)
    date_of_service_to = Column(Date, nullable=False)
    date_received = Column(Date, nullable=False)
    claim_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="received")
    total_billed = Column(Integer, nullable=False, default=0)  # cents
    total_approved = Column(Integer, nullable=False, default=0)  # cents
    total_member_liability = Column(Integer, nullable=False, default=0)  # cents
    total_scheme_liability = Column(Integer, nullable=False, default=0)  # cents
    is_pmb = Column(Boolean, default=False)
    adjudicated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    adjudicated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    scheme = relationship("Scheme", back_populates="claims")
    member = relationship("Member", back_populates="claims")
    dependant = relationship("Dependant")
    provider = relationship("Provider")
    adjudicated_by_user = relationship("User")
    lines = relationship("ClaimLine", back_populates="claim")
    adjudication_logs = relationship("ClaimAdjudicationLog", back_populates="claim")


class ClaimLine(Base):
    __tablename__ = "claim_lines"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    tariff_code = Column(String(20), nullable=False)
    description = Column(String(500), nullable=True)
    icd10_code = Column(String(20), nullable=True)
    nappi_code_id = Column(Integer, ForeignKey("nappi_codes.id"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    billed_amount = Column(Integer, nullable=False, default=0)  # cents
    approved_amount = Column(Integer, nullable=False, default=0)  # cents
    nhrpl_rate = Column(Integer, nullable=True)  # cents
    scheme_rate_cents = Column(Integer, nullable=True)  # plan-specific approved rate (NHRPL × multiplier)
    member_liability = Column(Integer, nullable=False, default=0)  # cents
    copayment_cents = Column(Integer, nullable=False, default=0)  # co-payment portion
    benefit_bucket = Column(String(30), nullable=True)
    # HOSPITAL | DAY_TO_DAY | SAVINGS | CHRONIC | ONCOLOGY | WELLNESS | PMB_RISK | MEMBER_LIABILITY
    rejection_reason_code = Column(String(20), nullable=True)
    rejection_reason_text = Column(String(500), nullable=True)
    is_pmb_line = Column(Boolean, default=False)
    is_pmb_override = Column(Boolean, default=False)  # TRUE if MSA s.29(1)(o) override applied

    claim = relationship("Claim", back_populates="lines")
    nappi = relationship("NappiCode")
