from app.models.auth import User, Scheme, AuditLog
from app.models.reference import ICD10Code, TariffCode, RejectionCode, PlanOption
from app.models.members import Member, Dependant, BenefitLimit, MemberStatusHistory
from app.models.providers import Provider
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.claims import Claim, ClaimLine
from app.models.underwriting import UnderwritingDecision, MemberConditionExclusion, EnrollmentQuestionnaire
from app.models.billing import NappiCode, ProviderNetwork, CopaymentRule, ChronicRegistration, Dispute, MemberContribution
from app.models.employers import EmployerGroup, MemberEmployerHistory
from app.models.intermediaries import Brokerage, Broker, BrokerCommissionScale, BrokerAppointment

# Load all authorisations modules that might have these
import app.models.authorisations
import app.models.billing
import app.models.claims
import app.models.employers
import app.models.intermediaries
import app.models.members
import app.models.providers
import app.models.reference
import app.models.underwriting

import importlib
import pkgutil
from pathlib import Path

# Auto-import all modules in models to ensure alembic sees everything
package_dir = Path(__file__).resolve().parent
for (_, module_name, _) in pkgutil.iter_modules([str(package_dir)]):
    if module_name not in ["__init__", "mixins"]:
        importlib.import_module(f"app.models.{module_name}")

__all__ = [
    "User", "Scheme", "AuditLog",
    "ICD10Code", "TariffCode", "RejectionCode", "PlanOption",
    "Member", "Dependant", "BenefitLimit", "MemberStatusHistory",
    "Provider",
    "Authorisation", "AuthorisationLine",
    "Claim", "ClaimLine",
    "UnderwritingDecision", "MemberConditionExclusion", "EnrollmentQuestionnaire",
    "NappiCode", "ProviderNetwork", "CopaymentRule", "ChronicRegistration", "Dispute",
    "MemberContribution",
    "EmployerGroup", "MemberEmployerHistory",
    "Brokerage", "Broker", "BrokerCommissionScale", "BrokerAppointment",
]
