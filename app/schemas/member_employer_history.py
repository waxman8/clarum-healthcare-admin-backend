# Pydantic schemas for MemberEmployerHistory
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class MemberEmployerHistoryBase(BaseModel):
    scheme_id: int
    member_id: int
    employer_group_id: int
    effective_date: date
    end_date: Optional[date] = None
    employment_status: str = "ACTIVE"
    payroll_reference: Optional[str] = None
    termination_reason: Optional[str] = None
    notes: Optional[str] = None


class MemberEmployerHistoryCreate(MemberEmployerHistoryBase):
    pass


class MemberEmployerHistoryUpdate(BaseModel):
    employer_group_id: Optional[int] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    employment_status: Optional[str] = None
    payroll_reference: Optional[str] = None
    termination_reason: Optional[str] = None
    notes: Optional[str] = None


class MemberEmployerHistoryRead(MemberEmployerHistoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    employer_name: Optional[str] = None  # populated by service layer

    class Config:
        from_attributes = True
