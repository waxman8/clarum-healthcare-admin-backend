from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Date, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)

    # --- Identity ---
    practice_number = Column(String(50), unique=True, nullable=False, index=True)
    registered_name = Column(String(255), nullable=True)   # legal entity name
    trading_name = Column(String(255), nullable=False)
    vat_number = Column(String(20), nullable=True)
    hpcsa_number = Column(String(20), nullable=True)       # Health Professions Council SA
    sapc_number = Column(String(20), nullable=True)        # SA Pharmacy Council
    dispensing_license = Column(Boolean, default=False)    # authorised to dispense medicine

    # --- Discipline ---
    discipline_code = Column(String(10), nullable=True, index=True)  # BHF standard code
    provider_category = Column(String(50), nullable=True)
    # INDIVIDUAL | GROUP_PRACTICE | HOSPITAL | DAY_CLINIC | PHARMACY |
    # LABORATORY | RADIOLOGY | OPTICAL | EMERGENCY

    # --- Contact ---
    telephone = Column(String(20), nullable=True)
    fax = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)      # kept for compat; prefer telephone
    website = Column(String(255), nullable=True)

    # --- Address ---
    address_line1 = Column(String(255), nullable=True)
    suburb = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    province = Column(String(50), nullable=True)
    postal_code = Column(String(10), nullable=True)
    latitude = Column(Numeric(10, 6), nullable=True)
    longitude = Column(Numeric(10, 6), nullable=True)
    physical_address = Column(Text, nullable=True)         # legacy JSON field

    # --- Banking (EFT) ---
    bank_name = Column(String(100), nullable=True)
    branch_code = Column(String(10), nullable=True)
    account_number = Column(String(30), nullable=True)
    account_type = Column(String(20), nullable=True)       # CURRENT | SAVINGS
    account_holder = Column(String(255), nullable=True)

    # --- Status & Flags ---
    is_active = Column(Boolean, default=True)
    contracted = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(String(500), nullable=True)
    blacklist_date = Column(Date, nullable=True)

    # --- Hospital-specific ---
    hospital_level = Column(Integer, nullable=True)        # 1 | 2 | 3
    bed_count = Column(Integer, nullable=True)
    icu_bed_count = Column(Integer, nullable=True)

    # --- Deprecated (authoritative DSP designation lives in provider_networks) ---
    is_dsp = Column(Boolean, default=False)
    provider_type = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    network_memberships = relationship("ProviderNetwork", back_populates="provider")
