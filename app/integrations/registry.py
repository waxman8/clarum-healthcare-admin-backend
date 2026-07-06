"""Runtime binding of adapter contracts to concrete implementations.

Default bindings are Mocks so a fresh checkout runs end-to-end with no
vendor credentials. Swap for a vendor implementation at app startup
(usually in `app.main` after config is loaded) or in a pytest fixture.

USAGE
    from app.integrations import ClaimsSwitch
    from app.integrations.registry import get

    def some_service(...):
        switch = get(ClaimsSwitch)
        switch.ingest_batch(...)

    # In a test fixture:
    from app.integrations.registry import bind
    bind(ClaimsSwitch, MyStubClaimsSwitch())
"""
from __future__ import annotations

from typing import Any

from app.integrations.contracts import (
    ClaimsSwitch,
    IdentityVerifier,
    MandateProvider,
    MessagingGateway,
    TaxFiler,
)
from app.integrations.mocks import (
    MockClaimsSwitch,
    MockIdentityVerifier,
    MockMandateProvider,
    MockMessagingGateway,
    MockTaxFiler,
)

_bindings: dict[type, Any] = {
    ClaimsSwitch:     MockClaimsSwitch(),
    MandateProvider:  MockMandateProvider(),
    IdentityVerifier: MockIdentityVerifier(),
    MessagingGateway: MockMessagingGateway(),
    TaxFiler:         MockTaxFiler(),
}


def get(contract: type) -> Any:
    """Return the currently-bound implementation for a contract."""
    if contract not in _bindings:
        raise KeyError(f"No binding for {contract.__name__}. Call bind() first.")
    return _bindings[contract]


def bind(contract: type, impl: Any) -> None:
    """Bind (or rebind) a concrete implementation to a contract."""
    _bindings[contract] = impl


def reset() -> None:
    """Reset all bindings back to their default Mock implementations.

    Useful in pytest between tests to prevent state leaking across cases.
    """
    _bindings.clear()
    _bindings.update({
        ClaimsSwitch:     MockClaimsSwitch(),
        MandateProvider:  MockMandateProvider(),
        IdentityVerifier: MockIdentityVerifier(),
        MessagingGateway: MockMessagingGateway(),
        TaxFiler:         MockTaxFiler(),
    })
