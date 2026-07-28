from typing import Optional, List
from fastapi import HTTPException
from app.repositories.beneficiary_nomination_repository import MemberNomineeRepository
from app.repositories.member import MemberRepository
from app.schemas.beneficiary_nomination import MemberNomineeCreate, MemberNomineeUpdate
from app.models.members import MemberNominee
from app.constants import MemberStatus


class MemberNomineeService:
    """Business-logic layer for MemberNominee."""

    def __init__(self, repo: MemberNomineeRepository, member_repo: MemberRepository):
        self.repo = repo
        self.member_repo = member_repo

    async def list_nominees(self, member_id: int, scheme_id: Optional[int] = None) -> List[MemberNominee]:
        """List nominees for a specific member."""
        # Note: repository list() might need to be filtered by member_id
        # The generated repo has a generic list, we can use that or add a specific method.
        # Let's assume we use the generic list and filter here or update the repo.
        items = await self.repo.list(scheme_id=scheme_id)
        return [i for i in items if i.member_id == member_id]

    async def create_nominee(self, payload: MemberNomineeCreate, scheme_id: Optional[int] = None) -> MemberNominee:
        """Create a new nominee with business rule validation."""
        # 1. Check member status
        member = await self.member_repo.get_by_id(payload.member_id, scheme_id=scheme_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        if member.status == MemberStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Cannot add nominees to a terminated member")

        # 2. Check nominee count
        existing_nominees = await self.list_nominees(payload.member_id, scheme_id=scheme_id)
        if len(existing_nominees) >= 4:
            raise HTTPException(status_code=400, detail="Maximum 4 nominees allowed per member")

        # 3. Check total allocation
        total_pct = sum(n.allocation_pct for n in existing_nominees) + payload.allocation_pct
        if total_pct > 100:
            raise HTTPException(status_code=400, detail=f"Total allocation cannot exceed 100% (current: {total_pct}%)")

        # Set scheme_id
        payload.scheme_id = scheme_id
        
        # Guardrail: Avoid logging ID number (handled by not logging here)
        return await self.repo.create(payload)

    async def sync_nominees(self, member_id: int, nominees: List[MemberNomineeCreate], scheme_id: Optional[int] = None) -> List[MemberNominee]:
        """Replace all nominees for a member in one transaction."""
        # 1. Check member status
        member = await self.member_repo.get_by_id(member_id, scheme_id=scheme_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        
        if member.status == MemberStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Cannot manage nominees of a terminated member")

        # 2. Validate new set
        if len(nominees) > 4:
            raise HTTPException(status_code=400, detail="Maximum 4 nominees allowed")
        
        total_pct = sum(n.allocation_pct for n in nominees)
        if total_pct != 0 and total_pct != 100:
            raise HTTPException(status_code=400, detail=f"Total allocation must be exactly 100% (current: {total_pct}%)")

        # 3. Delete existing
        existing = await self.list_nominees(member_id, scheme_id=scheme_id)
        for e in existing:
            await self.repo.delete(e.id, scheme_id=scheme_id)

        # 4. Create new
        created = []
        for n in nominees:
            n.member_id = member_id
            n.scheme_id = scheme_id
            created.append(await self.repo.create(n))
        
        return created

    async def update_nominee(self, item_id: int, payload: MemberNomineeUpdate, scheme_id: Optional[int] = None) -> MemberNominee:
        """Update a nominee with business rule validation."""
        existing = await self.repo.get(item_id, scheme_id=scheme_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Nominee not found")

        # 1. Check member status
        member = await self.member_repo.get_by_id(existing.member_id, scheme_id=scheme_id)
        if member.status == MemberStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Cannot update nominees of a terminated member")

        # 2. Check total allocation if pct is changing
        if payload.allocation_pct is not None:
            all_nominees = await self.list_nominees(existing.member_id, scheme_id=scheme_id)
            total_pct = sum(n.allocation_pct for n in all_nominees if n.id != item_id) + payload.allocation_pct
            if total_pct > 100:
                raise HTTPException(status_code=400, detail=f"Total allocation cannot exceed 100% (current: {total_pct}%)")

        return await self.repo.update(item_id, payload, scheme_id=scheme_id)

    async def delete_nominee(self, item_id: int, scheme_id: Optional[int] = None) -> bool:
        """Delete a nominee after checking member status."""
        existing = await self.repo.get(item_id, scheme_id=scheme_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Nominee not found")

        member = await self.member_repo.get_by_id(existing.member_id, scheme_id=scheme_id)
        if member.status == MemberStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Cannot delete nominees of a terminated member")

        return await self.repo.delete(item_id, scheme_id=scheme_id)
