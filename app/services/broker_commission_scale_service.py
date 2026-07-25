# Auto-generated service stub for BrokerCommissionScale
# Add business logic here; the router delegates to this layer.

from app.repositories.broker_commission_scale_repository import BrokerCommissionScaleRepository


import math
from datetime import date
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select, and_, or_
from app.repositories.broker_commission_scale_repository import BrokerCommissionScaleRepository
from app.models.intermediaries import BrokerCommissionScale
from app.models.auth import AuditLog
from app.schemas.broker_commission_scale import BrokerCommissionScaleCreate, BrokerCommissionScaleUpdate
from app.constants import RegulatoryLimits


class BrokerCommissionScaleService:
    """Business-logic layer for BrokerCommissionScale.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: BrokerCommissionScaleRepository):
        self.repo = repo

    async def _validate(self, payload: BrokerCommissionScaleCreate | BrokerCommissionScaleUpdate, scheme_id: int, current_id: Optional[int] = None):
        # 1. Cap validation
        if hasattr(payload, 'max_pmpm_cents') and payload.max_pmpm_cents is not None:
            vat_inclusive = getattr(payload, 'vat_inclusive', False)
            if isinstance(payload, BrokerCommissionScaleUpdate) and vat_inclusive is None:
                if current_id:
                    existing = await self.repo.get(current_id, scheme_id)
                    vat_inclusive = existing.vat_inclusive if existing else False
                else:
                    vat_inclusive = False
            
            max_allowed = RegulatoryLimits.CMS_REG28_MAX_PMPM_CENTS_EXCL_VAT
            if vat_inclusive:
                max_allowed = math.ceil(max_allowed * 1.15)
                
            if payload.max_pmpm_cents > max_allowed:
                raise HTTPException(status_code=400, detail=f"max_pmpm_cents exceeds CMS Reg 28 cap ({max_allowed} cents)")

        # 2. Overlap and Date range validation
        effective_from = getattr(payload, 'effective_from', None)
        effective_to = getattr(payload, 'effective_to', None)
        broker_id = getattr(payload, 'broker_id', None)
        
        if isinstance(payload, BrokerCommissionScaleUpdate) and current_id:
            existing = await self.repo.get(current_id, scheme_id)
            if not existing:
                return
            if effective_from is None: effective_from = existing.effective_from
            if effective_to is None and not payload.model_dump(exclude_unset=True).get('effective_to', False): effective_to = existing.effective_to
            elif payload.model_dump(exclude_unset=True).get('effective_to') is None: effective_to = None
            
            if broker_id is None and not payload.model_dump(exclude_unset=True).get('broker_id', False): broker_id = existing.broker_id
            elif payload.model_dump(exclude_unset=True).get('broker_id') is None: broker_id = None
            
        if effective_from and effective_to and effective_to < effective_from:
            raise HTTPException(status_code=400, detail="effective_to cannot be before effective_from")
            
        if effective_from:
            query = select(BrokerCommissionScale).where(
                BrokerCommissionScale.scheme_id == scheme_id,
                BrokerCommissionScale.broker_id == broker_id
            )
            if current_id:
                query = query.where(BrokerCommissionScale.id != current_id)
                
            # Overlap condition: (A.start < B.end OR B.end IS NULL) AND (A.end > B.start OR A.end IS NULL)
            conds = []
            if effective_to:
                conds.append(BrokerCommissionScale.effective_from < effective_to)
            
            conds.append(or_(
                BrokerCommissionScale.effective_to > effective_from,
                BrokerCommissionScale.effective_to.is_(None)
            ))
            
            query = query.where(and_(*conds))
            
            result = await self.repo.db.execute(query)
            if result.scalars().first():
                raise HTTPException(status_code=400, detail="Overlapping commission scale period for this broker")

    async def list(self, scheme_id: Optional[int] = None, skip: int = 0, limit: int = 100):
        return await self.repo.list(scheme_id, skip, limit)
        
    async def get(self, item_id: int, scheme_id: Optional[int] = None):
        return await self.repo.get(item_id, scheme_id)

    async def create(self, payload: BrokerCommissionScaleCreate, scheme_id: int, user_id: int):
        payload.scheme_id = scheme_id
        await self._validate(payload, scheme_id)
        obj = await self.repo.create(payload)
        
        audit = AuditLog(
            user_id=user_id,
            entity_type="BrokerCommissionScale",
            entity_id=obj.id,
            action="CREATE",
            new_value=payload.model_dump_json(exclude_unset=True)
        )
        self.repo.db.add(audit)
        await self.repo.db.flush()
        return obj

    async def update(self, item_id: int, payload: BrokerCommissionScaleUpdate, scheme_id: int, user_id: int):
        existing = await self.repo.get(item_id, scheme_id)
        if not existing:
            return None
            
        old_data = {
            "effective_from": str(existing.effective_from) if existing.effective_from else None,
            "effective_to": str(existing.effective_to) if existing.effective_to else None,
            "max_pmpm_cents": existing.max_pmpm_cents,
            "commission_amount_cents": existing.commission_amount_cents,
            "vat_inclusive": existing.vat_inclusive,
            "broker_id": existing.broker_id,
            "member_type": existing.member_type,
            "notes": existing.notes
        }
        
        await self._validate(payload, scheme_id, item_id)
        obj = await self.repo.update(item_id, payload, scheme_id)
        
        import json
        audit = AuditLog(
            user_id=user_id,
            entity_type="BrokerCommissionScale",
            entity_id=obj.id,
            action="UPDATE",
            old_value=json.dumps(old_data),
            new_value=payload.model_dump_json(exclude_unset=True)
        )
        self.repo.db.add(audit)
        await self.repo.db.flush()
        return obj
        
    async def delete(self, item_id: int, scheme_id: int, user_id: int):
        existing = await self.repo.get(item_id, scheme_id)
        if not existing:
            return False
            
        deleted = await self.repo.delete(item_id, scheme_id)
        if deleted:
            audit = AuditLog(
                user_id=user_id,
                entity_type="BrokerCommissionScale",
                entity_id=item_id,
                action="DELETE"
            )
            self.repo.db.add(audit)
            await self.repo.db.flush()
            
        return deleted
