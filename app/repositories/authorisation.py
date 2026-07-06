"""Authorisation repository — all Authorisation/AuthorisationLine queries in one place."""
import math
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.authorisations import Authorisation, AuthorisationLine


class AuthorisationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Base query with eager-loaded relations
    # ------------------------------------------------------------------
    def _base_query(self):
        return select(Authorisation).options(
            selectinload(Authorisation.member),
            selectinload(Authorisation.requesting_provider),
            selectinload(Authorisation.lines),
            selectinload(Authorisation.dependant),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_by_id(self, auth_id: int) -> Optional[Authorisation]:
        result = await self.db.execute(
            self._base_query().where(Authorisation.id == auth_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        scheme_id: Optional[int],
        status: Optional[str] = None,
        member_id: Optional[int] = None,
        dependant_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        from app.models.members import Member as MemberModel

        q = self._base_query()
        count_base = select(Authorisation)

        # Scope to scheme via member join
        if scheme_id is not None:
            q = q.join(MemberModel, Authorisation.member_id == MemberModel.id).where(
                MemberModel.scheme_id == scheme_id
            )
            count_base = count_base.join(
                MemberModel, Authorisation.member_id == MemberModel.id
            ).where(MemberModel.scheme_id == scheme_id)

        if status:
            q = q.where(Authorisation.status == status)
            count_base = count_base.where(Authorisation.status == status)
        if member_id:
            q = q.where(Authorisation.member_id == member_id)
            count_base = count_base.where(Authorisation.member_id == member_id)
        if dependant_id:
            q = q.where(Authorisation.dependant_id == dependant_id)
            count_base = count_base.where(Authorisation.dependant_id == dependant_id)

        q = q.order_by(Authorisation.created_at.desc())

        count_q = select(func.count()).select_from(count_base.subquery())
        total = (await self.db.execute(count_q)).scalar()

        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size) if total > 0 else 1,
        }

    async def count_open(self, scheme_id: int) -> int:
        from app.models.members import Member as MemberModel
        from app.constants import AuthStatus
        result = await self.db.execute(
            select(func.count(Authorisation.id))
            .join(MemberModel, Authorisation.member_id == MemberModel.id)
            .where(
                MemberModel.scheme_id == scheme_id,
                Authorisation.status == AuthStatus.PENDING,
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Sequence for auth number
    # ------------------------------------------------------------------
    async def next_sequence(self) -> int:
        result = await self.db.execute(select(func.count(Authorisation.id)))
        return (result.scalar() or 0) + 1

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def create(self, auth: Authorisation) -> Authorisation:
        self.db.add(auth)
        await self.db.flush()
        return auth

    async def save(self) -> None:
        await self.db.commit()
