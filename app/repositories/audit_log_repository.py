from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select, func, and_
from sqlalchemy.orm import selectinload
from app.models.auth import AuditLog, User
from typing import Optional, List, Tuple
from datetime import datetime


class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        scheme_id: Optional[int],
        actor_id: Optional[int] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 25
    ) -> Tuple[List[AuditLog], int]:
        filters = []
        if scheme_id is not None:
            filters.append(AuditLog.scheme_id == scheme_id)

        if actor_id:
            filters.append(AuditLog.user_id == actor_id)
        if action:
            filters.append(AuditLog.action == action)
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if entity_id:
            filters.append(AuditLog.entity_id == entity_id)
        if date_from:
            filters.append(AuditLog.timestamp >= date_from)
        if date_to:
            filters.append(AuditLog.timestamp <= date_to)

        # Count total
        count_stmt = select(func.count()).select_from(AuditLog).where(and_(*filters))
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0
        
        # Fetch items with eager loaded user
        stmt = select(AuditLog)\
            .options(selectinload(AuditLog.user))\
            .where(and_(*filters))\
            .order_by(desc(AuditLog.timestamp))\
            .offset((page - 1) * page_size)\
            .limit(page_size)
            
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        # Populate actor_name for convenience
        for item in items:
            if item.user:
                item.actor_name = item.user.full_name
            else:
                item.actor_name = "System"

        return items, total

    async def get(self, scheme_id: Optional[int], audit_log_id: int) -> Optional[AuditLog]:
        filters = [AuditLog.id == audit_log_id]
        if scheme_id is not None:
            filters.append(AuditLog.scheme_id == scheme_id)
            
        stmt = select(AuditLog).options(selectinload(AuditLog.user)).where(and_(*filters))
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if item and item.user:
            item.actor_name = item.user.full_name
        elif item:
            item.actor_name = "System"
            
        return item

    async def get_entity_types(self, scheme_id: Optional[int]) -> List[str]:
        filters = []
        if scheme_id is not None:
            filters.append(AuditLog.scheme_id == scheme_id)
            
        stmt = select(AuditLog.entity_type).where(and_(*filters)).distinct().order_by(AuditLog.entity_type)
        result = await self.db.execute(stmt)
        return result.scalars().all()
