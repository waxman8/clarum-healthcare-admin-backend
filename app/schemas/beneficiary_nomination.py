# Auto-generated Pydantic schemas for MemberNominee
from datetime import date, datetime  # noqa: F401
from decimal import Decimal           # noqa: F401
from typing import Optional
from pydantic import BaseModel, field_validator


class MemberNomineeBase(BaseModel):
    member_id: int
    full_name: str
    id_number: str
    relationship: str
    allocation_pct: int

    @field_validator("allocation_pct")
    @classmethod
    def validate_allocation(cls, v: int) -> int:
        if v < 0 or v > 100:
            raise ValueError("Allocation percentage must be between 0 and 100")
        return v


class MemberNomineeCreate(MemberNomineeBase):
    scheme_id: Optional[int] = None


class MemberNomineeUpdate(BaseModel):
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    relationship: Optional[str] = None
    allocation_pct: Optional[int] = None

    @field_validator("allocation_pct")
    @classmethod
    def validate_allocation(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Allocation percentage must be between 0 and 100")
        return v


class MemberNomineeRead(MemberNomineeBase):
    id: int
    scheme_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
