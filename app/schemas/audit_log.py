from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: Optional[int] = None
    entity_label: Optional[str] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime
    user_id: Optional[int] = None
    user_name: Optional[str] = None


class PaginatedAuditLogResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int
