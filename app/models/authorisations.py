from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Authorisation(Base):
    __tablename__ = "authorisations"

    id = Column(Integer, primary_key=True, index=True)
    auth_number = Column(String(50), unique=True, nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    dependant_id = Column(Integer, ForeignKey("dependants.id"), nullable=True)
    requesting_provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    icd10_codes = Column(Text, nullable=True)  # JSON array
    procedure_codes = Column(Text, nullable=True)  # JSON array
    auth_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    approved_days = Column(Integer, nullable=True)
    clinical_notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    modified_date = Column(DateTime(timezone=True), nullable=True)
    modified_user = Column(Integer, ForeignKey("users.id"), nullable=True)

    member = relationship("Member", back_populates="authorisations")
    dependant = relationship("Dependant")
    requesting_provider = relationship("Provider")
    created_by_user = relationship("User", foreign_keys=[created_by])
    lines = relationship("AuthorisationLine", back_populates="authorisation")


class AuthorisationLine(Base):
    __tablename__ = "authorisation_lines"

    id = Column(Integer, primary_key=True, index=True)
    auth_id = Column(Integer, ForeignKey("authorisations.id"), nullable=False)
    tariff_code = Column(String(20), nullable=False)
    description = Column(String(500), nullable=True)
    quantity_requested = Column(Integer, nullable=False, default=1)
    quantity_approved = Column(Integer, nullable=True)
    reason_declined = Column(String(500), nullable=True)

    authorisation = relationship("Authorisation", back_populates="lines")
