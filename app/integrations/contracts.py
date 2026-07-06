"""Adapter contracts.

Each contract is a `typing.Protocol` — implementations don't need to inherit,
they just need to match the shape. Static checkers keep the surface honest.

Contracts here today:
  * ClaimsSwitch       — HealthBridge / MediKredit / MediSwitch inbound claim batches
  * MandateProvider    — DebiCheck debit-order mandate lifecycle
  * IdentityVerifier   — DHA HANIS SA ID verification
  * MessagingGateway   — SMS + email outbound
  * TaxFiler           — SARS IT3(b) generation and submission

Add new contracts here first; only then wire a mock and a vendor impl.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Claims switch — HealthBridge / MediKredit / MediSwitch
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaimBatch:
    """One inbound batch envelope from a claims switch."""
    switch_reference: str
    provider_practice_number: str
    payload: dict[str, Any]  # raw switch envelope, decoded to dict


class ClaimsSwitch(Protocol):
    def ingest_batch(self, batch: ClaimBatch) -> str:
        """Accept a batch. Returns the internal batch reference to persist."""
        ...

    def acknowledge(self, batch_ref: str, status: str, detail: str | None = None) -> None:
        """Send accept / reject acknowledgement back to the switch."""
        ...


# ---------------------------------------------------------------------------
# Debit-order / DebiCheck mandate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MandateRequest:
    member_id: int
    bank_account_number: str
    branch_code: str
    amount_cents: int
    frequency: str  # MONTHLY | WEEKLY


class MandateProvider(Protocol):
    def create_mandate(self, req: MandateRequest) -> str:
        """Create a DebiCheck mandate. Returns the mandate reference."""
        ...

    def verify_mandate(self, mandate_ref: str) -> bool:
        """Confirm the mandate is active and authenticated."""
        ...

    def cancel_mandate(self, mandate_ref: str, reason: str) -> None: ...


# ---------------------------------------------------------------------------
# Identity verification — DHA HANIS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityRecord:
    id_number: str
    first_name: str
    surname: str
    date_of_birth: date
    verified: bool


class IdentityVerifier(Protocol):
    def verify_id_number(self, id_number: str) -> IdentityRecord:
        """Verify a SA ID against HANIS. Raises for invalid / not found."""
        ...


# ---------------------------------------------------------------------------
# Messaging — SMS + email outbound
# ---------------------------------------------------------------------------

class MessagingGateway(Protocol):
    def send_sms(self, cell_number: str, body: str) -> str:
        """Queue an SMS. Returns provider message reference."""
        ...

    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> str:
        """Queue an email. Returns provider message reference."""
        ...


# ---------------------------------------------------------------------------
# Tax filing — SARS IT3(b)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaxCertificate:
    member_id: int
    tax_year: int
    total_contributions_cents: int
    dependant_count: int


class TaxFiler(Protocol):
    def generate_certificate(self, member_id: int, tax_year: int) -> TaxCertificate: ...

    def submit_batch(self, certificates: list[TaxCertificate]) -> str:
        """Submit a batch to SARS. Returns SARS submission reference."""
        ...
