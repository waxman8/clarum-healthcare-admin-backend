"""External-system adapter contracts.

Every external system we talk to has:
  * A contract (Protocol) in `contracts.py` — the vocabulary services depend on.
  * A `Mock<X>` implementation in `mocks.py` — deterministic, no network,
    used by pytest and local dev.
  * A registry binding in `registry.py` — swappable per environment.
  * (Later) a vendor implementation alongside: `healthbridge.py`, `debicheck.py`, ...

Rule: services import contracts, never vendor clients.
    from app.integrations import ClaimsSwitch
    from app.integrations.registry import get
    switch: ClaimsSwitch = get(ClaimsSwitch)
"""
from app.integrations.contracts import (
    ClaimBatch,
    ClaimsSwitch,
    IdentityRecord,
    IdentityVerifier,
    MandateProvider,
    MandateRequest,
    MessagingGateway,
    TaxCertificate,
    TaxFiler,
)

__all__ = [
    "ClaimBatch",
    "ClaimsSwitch",
    "IdentityRecord",
    "IdentityVerifier",
    "MandateProvider",
    "MandateRequest",
    "MessagingGateway",
    "TaxCertificate",
    "TaxFiler",
]
