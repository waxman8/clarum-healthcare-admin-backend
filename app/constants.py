"""
Central constants for the healthcare-admin platform.

All role strings, status values, benefit buckets, and member types live here.
Never use bare string literals for these in routers, services, or seeds.
"""


# ---------------------------------------------------------------------------
# User roles
# ---------------------------------------------------------------------------
class Role:
    SUPER_ADMIN = "super_admin"
    SCHEME_ADMIN = "scheme_admin"
    CLAIMS_PROCESSOR = "claims_processor"
    AUTHORISATION_OFFICER = "authorisation_officer"
    FINANCE_OFFICER = "finance_officer"
    FINANCE_ADMIN = "finance_admin"
    CALL_CENTRE_AGENT = "call_centre_agent"

    ALL = [
        SUPER_ADMIN,
        SCHEME_ADMIN,
        CLAIMS_PROCESSOR,
        AUTHORISATION_OFFICER,
        FINANCE_OFFICER,
        CALL_CENTRE_AGENT,
    ]

    # Common permission groups
    CAN_ADJUDICATE = [SUPER_ADMIN, SCHEME_ADMIN, CLAIMS_PROCESSOR]
    CAN_APPROVE_AUTH = [SUPER_ADMIN, SCHEME_ADMIN, AUTHORISATION_OFFICER]
    CAN_DECIDE_CHRONIC = [SUPER_ADMIN, SCHEME_ADMIN, CLAIMS_PROCESSOR]
    CAN_RESOLVE_DISPUTE = [SUPER_ADMIN, SCHEME_ADMIN]
    CAN_CHANGE_THEME = [SUPER_ADMIN, SCHEME_ADMIN]
    CAN_OVERRIDE_CLAIM = [SUPER_ADMIN, SCHEME_ADMIN]


# ---------------------------------------------------------------------------
# Member statuses
# ---------------------------------------------------------------------------
class MemberStatus:
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    LAPSED = "lapsed"
    CANCELLED = "cancelled"

    ALL = [ACTIVE, PENDING, SUSPENDED, LAPSED, CANCELLED]


# ---------------------------------------------------------------------------
# Member communication preferences
# ---------------------------------------------------------------------------
class CommunicationChannel:
    SMS = "SMS"
    EMAIL = "EMAIL"
    POST = "POST"

    ALL = [SMS, EMAIL, POST]


class CommunicationCategory:
    BILLING = "BILLING"
    WELLNESS = "WELLNESS"
    GENERAL = "GENERAL"

    ALL = [BILLING, WELLNESS, GENERAL]


# ---------------------------------------------------------------------------
# Claim statuses
# ---------------------------------------------------------------------------
class ClaimStatus:
    RECEIVED = "received"
    IN_ADJUDICATION = "in_adjudication"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIAL = "partial"
    PAID = "paid"


# ---------------------------------------------------------------------------
# Authorisation statuses
# ---------------------------------------------------------------------------
class AuthStatus:
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Chronic registration statuses  (UPPERCASE — CDL domain convention)
# ---------------------------------------------------------------------------
class ChronicStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Dispute statuses  (UPPERCASE — matches CMS reporting convention)
# ---------------------------------------------------------------------------
class DisputeStatus:
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    UPHELD = "UPHELD"
    DISMISSED = "DISMISSED"
    ESCALATED_TO_CMS = "ESCALATED_TO_CMS"

    OPEN_STATUSES = [OPEN, UNDER_REVIEW]
    VALID_RESOLUTIONS = [UPHELD, DISMISSED, ESCALATED_TO_CMS]


# ---------------------------------------------------------------------------
# Benefit buckets
# ---------------------------------------------------------------------------
class BenefitBucket:
    HOSPITAL = "HOSPITAL"
    DAY_TO_DAY = "DAY_TO_DAY"
    SAVINGS = "SAVINGS"
    CHRONIC = "CHRONIC"
    ONCOLOGY = "ONCOLOGY"
    WELLNESS = "WELLNESS"
    PMB_RISK = "PMB_RISK"
    MEMBER_LIABILITY = "MEMBER_LIABILITY"

    # Buckets that decrement benefit_balance (not funded from risk/member pocket)
    TRACKED = [HOSPITAL, DAY_TO_DAY, SAVINGS, CHRONIC, ONCOLOGY, WELLNESS]
    NOT_DECREMENTED = [PMB_RISK, MEMBER_LIABILITY]


# ---------------------------------------------------------------------------
# Contribution member types
# ---------------------------------------------------------------------------
class MemberType:
    PRINCIPAL = "PRINCIPAL"
    ADULT_DEPENDANT = "ADULT_DEPENDANT"
    CHILD = "CHILD"
    CHILD_FREE = "CHILD_FREE"  # informational row — children beyond 3-child cap


# ---------------------------------------------------------------------------
# Adjudication pipeline internal statuses
# ---------------------------------------------------------------------------
class PipelineStatus:
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    FLAG = "FLAG"
    INFO = "INFO"
    OVERRIDE = "OVERRIDE"

    ACTIVE = [PENDING, FLAG]   # lines still being evaluated
    TERMINAL = [PASS, FAIL]    # lines with a final outcome


# ---------------------------------------------------------------------------
# Plan day-to-day types
# ---------------------------------------------------------------------------
class DayToDayType:
    LIMIT = "LIMIT"
    SAVINGS = "SAVINGS"
    NONE = "NONE"


# ---------------------------------------------------------------------------
# Hospital network types
# ---------------------------------------------------------------------------
class HospitalNetwork:
    OPEN = "OPEN"
    PRIME = "PRIME"
    COMPACT = "COMPACT"


# ---------------------------------------------------------------------------
# Copayment types
# ---------------------------------------------------------------------------
class CopaymentType:
    PERCENTAGE = "PERCENTAGE"
    RAND_AMOUNT = "RAND_AMOUNT"
