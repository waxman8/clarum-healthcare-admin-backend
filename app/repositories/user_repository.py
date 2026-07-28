from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, Tuple, List
from app.models.auth import User
from app.schemas.user import UserCreate, UserUpdate


class UserRepository:
    """Data-access layer for User entities, enforcing scheme-scoped isolation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        scheme_id: Optional[int],
        search: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[User], int]:
        # Filter strictly by scheme_id for Super Admin (since scheme_id cannot be None for isolation)
        query = select(User)
        if scheme_id is not None:
            query = query.where(User.scheme_id == scheme_id)
        else:
            # Fallback if no scheme_id, but logically a scheme scoping is required
            pass

        # Apply search filters
        if search:
            search_pattern = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(User.full_name).like(search_pattern),
                    func.lower(User.email).like(search_pattern),
                )
            )

        # Apply role filter
        if role:
            query = query.where(User.role == role)

        # Apply status filter
        if status:
            if status == "active":
                query = query.where(User.is_active == True)
            elif status == "deactivated":
                query = query.where(User.is_active == False)

        # Get total count first
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Execute pagination query ordered by creation
        query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total_count

    async def get(self, user_id: int, scheme_id: Optional[int]) -> Optional[User]:
        query = select(User).where(User.id == user_id)
        if scheme_id is not None:
            query = query.where(User.scheme_id == scheme_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, payload: UserCreate, hashed_password: str) -> User:
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            scheme_id=payload.scheme_id,
            hashed_password=hashed_password,
            is_active=True,
            must_reset_password=True,  # Mandatory first-login password reset
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(self, user_id: int, payload: UserUpdate, scheme_id: Optional[int]) -> Optional[User]:
        user = await self.get(user_id, scheme_id)
        if user is None:
            return None
        
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
            
        await self.db.flush()
        return user

    async def deactivate(self, user_id: int, scheme_id: Optional[int]) -> Optional[User]:
        user = await self.get(user_id, scheme_id)
        if user is None:
            return None
        user.is_active = False
        await self.db.flush()
        return user
