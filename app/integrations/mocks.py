"""In-memory Mock implementations of every adapter contract.

Used by:
  * pytest — bind these in a fixture so tests never hit real vendors.
  * local dev — the default binding in `registry.py` is a mock, so a fresh
    checkout runs end-to-end with no vendor credentials.

Behaviour:
  * Deterministic — sequential MOCK-* references so tests can assert.
  * Side-effect log kept on the instance for test assertions
    (e.g. `MockMessagingGateway().sms_log`).
  * No network I/O ever.
"""
from __future__ import annotations

from datetime import date
from itertools import count

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


class MockClaimsSwitch(ClaimsSwitch):
    def __init__(self) -> None:
        self._seq = count(1)
        self.received: list[ClaimBatch] = []
        self.acks: list[tuple[str, str, str | None]] = []

    def ingest_batch(self, batch: ClaimBatch) -> str:
        self.received.append(batch)
        return f"MOCK-BATCH-{next(self._seq):06d}"

    def acknowledge(self, batch_ref: str, status: str, detail: str | None = None) -> None:
        self.acks.append((batch_ref, status, detail))


class MockMandateProvider(MandateProvider):
    def __init__(self) -> None:
        self._seq = count(1)
        self.mandates: dict[str, MandateRequest] = {}
        self.cancelled: set[str] = set()

    def create_mandate(self, req: MandateRequest) -> str:
        ref = f"MOCK-MND-{next(self._seq):06d}"
        self.mandates[ref] = req
        return ref

    def verify_mandate(self, mandate_ref: str) -> bool:
        return mandate_ref in self.mandates and mandate_ref not in self.cancelled

    def cancel_mandate(self, mandate_ref: str, reason: str) -> None:
        self.cancelled.add(mandate_ref)


class MockIdentityVerifier(IdentityVerifier):
    def verify_id_number(self, id_number: str) -> IdentityRecord:
        return IdentityRecord(
            id_number=id_number,
            first_name="MOCK",
            surname="MEMBER",
            date_of_birth=date(1990, 1, 1),
            verified=True,
        )


class MockMessagingGateway(MessagingGateway):
    def __init__(self) -> None:
        self._seq = count(1)
        self.sms_log: list[tuple[str, str]] = []
        self.email_log: list[tuple[str, str, str, str]] = []

    def send_sms(self, cell_number: str, body: str) -> str:
        self.sms_log.append((cell_number, body))
        return f"MOCK-SMS-{next(self._seq):06d}"

    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> str:
        self.email_log.append((to, subject, body_html, body_text))
        return f"MOCK-EMAIL-{next(self._seq):06d}"


class MockTaxFiler(TaxFiler):
    def __init__(self) -> None:
        self._seq = count(1)
        self.submitted: list[list[TaxCertificate]] = []

    def generate_certificate(self, member_id: int, tax_year: int) -> TaxCertificate:
        return TaxCertificate(
            member_id=member_id,
            tax_year=tax_year,
            total_contributions_cents=0,
            dependant_count=0,
        )

    def submit_batch(self, certificates: list[TaxCertificate]) -> str:
        self.submitted.append(list(certificates))
        return f"MOCK-SARS-{next(self._seq):06d}"
