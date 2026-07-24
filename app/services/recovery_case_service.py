from datetime import date
from typing import Optional

from app.constants import RecoveryStatus, RecoveryType
from app.models.auth import AuditLog, User
from app.models.recovery import RecoveryCase, RecoveryCaseClaimLink, RecoveryReceipt
from app.repositories.recovery_case_repository import RecoveryCaseRepository
from app.schemas.recovery import RecoveryCaseCreate, RecoveryClaimLinkCreate, RecoveryTransitionCreate


class RecoveryCaseError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class RecoveryCaseService:
    def __init__(self, repo: RecoveryCaseRepository):
        self.repo = repo

    async def create(self, payload: RecoveryCaseCreate, scheme_id: int, user: User) -> RecoveryCase:
        if payload.recovery_type not in RecoveryType.ALL:
            raise RecoveryCaseError("Invalid recovery type")
        case = RecoveryCase(**payload.model_dump(), scheme_id=scheme_id, status=RecoveryStatus.IDENTIFIED, created_by=user.id, updated_by=user.id)
        await self.repo.add(case)
        self._audit(user, case.id, "create", "Recovery case created")
        return case

    async def link_claim(self, case_id: int, payload: RecoveryClaimLinkCreate, scheme_id: int, user: User) -> RecoveryCaseClaimLink:
        case = await self._case_or_404(case_id, scheme_id)
        if case.status in RecoveryStatus.TERMINAL:
            raise RecoveryCaseError("Cannot change a closed recovery case")
        claim = await self.repo.get_claim(payload.claim_id, scheme_id)
        if not claim:
            raise RecoveryCaseError("Claim not found", 404)
        if await self.repo.find_link(case_id, payload.claim_id, scheme_id):
            raise RecoveryCaseError("Claim is already linked to this recovery case")
        links = await self.repo.get_links(case_id, scheme_id)
        if sum(link.allocation_cents for link in links) + payload.allocation_cents > case.expected_cents:
            raise RecoveryCaseError("Claim allocations cannot exceed the expected recovery amount")
        available = max(claim.total_approved - claim.recovered_cents, 0)
        if payload.allocation_cents > available:
            raise RecoveryCaseError("Claim allocation exceeds the unrecovered claim amount")
        link = RecoveryCaseClaimLink(**payload.model_dump(), recovery_case_id=case.id, scheme_id=scheme_id, created_by=user.id, updated_by=user.id)
        await self.repo.add(link)
        self._audit(user, case.id, "link_claim", "Claim linked to recovery case")
        return link

    async def transition(self, case_id: int, payload: RecoveryTransitionCreate, scheme_id: int, user: User) -> RecoveryCase:
        case = await self._case_or_404(case_id, scheme_id)
        allowed = {
            RecoveryStatus.IDENTIFIED: [RecoveryStatus.SUBMITTED, RecoveryStatus.DECLINED, RecoveryStatus.WRITTEN_OFF],
            RecoveryStatus.SUBMITTED: [RecoveryStatus.PARTIALLY_RECEIVED, RecoveryStatus.RECEIVED, RecoveryStatus.DECLINED, RecoveryStatus.WRITTEN_OFF],
            RecoveryStatus.PARTIALLY_RECEIVED: [RecoveryStatus.PARTIALLY_RECEIVED, RecoveryStatus.RECEIVED, RecoveryStatus.WRITTEN_OFF],
        }
        if payload.status not in allowed.get(case.status, []):
            raise RecoveryCaseError("Illegal recovery-case transition")
        if payload.status in [RecoveryStatus.PARTIALLY_RECEIVED, RecoveryStatus.RECEIVED]:
            if payload.receipt_cents is None:
                raise RecoveryCaseError("A receipt amount is required for this transition")
            await self._record_receipt(case, payload.receipt_cents, payload.received_on or date.today(), scheme_id, user)
            if payload.status == RecoveryStatus.RECEIVED and case.recovered_cents != case.expected_cents:
                raise RecoveryCaseError("A case can only be marked received when fully recovered")
        case.status = payload.status
        case.status_reason = payload.reason
        case.status_changed_by = user.id
        case.updated_by = user.id
        await self.repo.add(case)
        self._audit(user, case.id, "transition", "Recovery case status changed", payload.reason)
        return case

    async def detail(self, case_id: int, scheme_id: int) -> tuple[RecoveryCase, list[RecoveryCaseClaimLink], list[RecoveryReceipt]]:
        case = await self._case_or_404(case_id, scheme_id)
        return case, await self.repo.get_links(case_id, scheme_id), await self.repo.get_receipts(case_id, scheme_id)

    async def _record_receipt(self, case: RecoveryCase, amount: int, received_on: date, scheme_id: int, user: User) -> None:
        if amount > case.expected_cents - case.recovered_cents:
            raise RecoveryCaseError("Receipt exceeds the outstanding recovery amount")
        remaining = amount
        for link in await self.repo.get_links(case.id, scheme_id):
            available = link.allocation_cents - link.recovered_cents
            applied = min(available, remaining)
            if applied:
                claim = await self.repo.get_claim(link.claim_id, scheme_id)
                if not claim:
                    raise RecoveryCaseError("Linked claim not found", 404)
                link.recovered_cents += applied
                link.updated_by = user.id
                claim.recovered_cents += applied
                await self.repo.add(link)
                await self.repo.add(claim)
                remaining -= applied
            if remaining == 0:
                break
        if remaining:
            raise RecoveryCaseError("Receipt cannot exceed linked-claim allocations")
        case.recovered_cents += amount
        receipt = RecoveryReceipt(recovery_case_id=case.id, scheme_id=scheme_id, amount_cents=amount, received_on=received_on, created_by=user.id, updated_by=user.id)
        await self.repo.add(receipt)

    async def _case_or_404(self, case_id: int, scheme_id: int) -> RecoveryCase:
        case = await self.repo.get(case_id, scheme_id)
        if not case:
            raise RecoveryCaseError("Recovery case not found", 404)
        return case

    def _audit(self, user: User, case_id: int, action: str, summary: str, reason: Optional[str] = None) -> None:
        self.repo.db.add(AuditLog(user_id=user.id, entity_type="recovery_case", entity_id=case_id, action=action, new_value=summary, user_role=user.role, reason=reason))
