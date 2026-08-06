from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AuditLogBase(BaseModel):
    user_id: Optional[int] = None
    timestamp: datetime
    entity_type: str
    entity_id: Optional[int] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    event_id: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    is_pmb_override: bool = False
    claim_rejection_code: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogResponse(AuditLogBase):
    id: int
    scheme_id: int
    actor_name: Optional[str] = None  # To be populated by repository


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
