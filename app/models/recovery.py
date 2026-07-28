from datetime import date

from sqlalchemy import Column, Date, Integer, String

from app.database import Base
from app.models.mixins import Auditable, MultiTenant, StatusHistory


class RecoveryCase(MultiTenant, Auditable, StatusHistory, Base):
    __tablename__ = "recovery_cases"

    id = Column(Integer, primary_key=True, index=True)
    recovery_type = Column(String(20), nullable=False, index=True)
    third_party_name = Column(String(255), nullable=False)
    third_party_reference = Column(String(100), nullable=True)
    expected_cents = Column(Integer, nullable=False)
    recovered_cents = Column(Integer, nullable=False, default=0)


class RecoveryCaseClaimLink(MultiTenant, Auditable, Base):
    __tablename__ = "recovery_case_claim_links"

    id = Column(Integer, primary_key=True, index=True)
    recovery_case_id = Column(Integer, nullable=False, index=True)
    claim_id = Column(Integer, nullable=False, index=True)
    allocation_cents = Column(Integer, nullable=False)
    recovered_cents = Column(Integer, nullable=False, default=0)


class RecoveryReceipt(MultiTenant, Auditable, Base):
    __tablename__ = "recovery_receipts"

    id = Column(Integer, primary_key=True, index=True)
    recovery_case_id = Column(Integer, nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    received_on = Column(Date, nullable=False, default=date.today)
