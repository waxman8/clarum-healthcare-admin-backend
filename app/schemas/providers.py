from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class ProviderCreate(BaseModel):
    practice_number: str
    registered_name: Optional[str] = None
    trading_name: str
    vat_number: Optional[str] = None
    hpcsa_number: Optional[str] = None
    sapc_number: Optional[str] = None
    dispensing_license: bool = False
    discipline_code: Optional[str] = None
    provider_category: Optional[str] = None
    provider_type: Optional[str] = None        # legacy
    telephone: Optional[str] = None
    fax: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None        # legacy
    website: Optional[str] = None
    address_line1: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    contracted: bool = False
    is_dsp: bool = False                       # deprecated; set via provider_networks


class ProviderUpdate(BaseModel):
    registered_name: Optional[str] = None
    trading_name: Optional[str] = None
    vat_number: Optional[str] = None
    hpcsa_number: Optional[str] = None
    sapc_number: Optional[str] = None
    dispensing_license: Optional[bool] = None
    discipline_code: Optional[str] = None
    provider_category: Optional[str] = None
    provider_type: Optional[str] = None
    telephone: Optional[str] = None
    fax: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    contracted: Optional[bool] = None
    is_active: Optional[bool] = None
    # Banking — role-gated in router (finance_officer / super_admin only)
    bank_name: Optional[str] = None
    branch_code: Optional[str] = None
    account_number: Optional[str] = None
    account_type: Optional[str] = None
    account_holder: Optional[str] = None
    # Hospital-specific
    hospital_level: Optional[int] = None
    bed_count: Optional[int] = None
    icu_bed_count: Optional[int] = None


class BlacklistRequest(BaseModel):
    reason: str
    blacklist_date: Optional[date] = None


class ProviderSummaryResponse(BaseModel):
    """Lightweight response for list views — no banking details."""
    id: int
    practice_number: str
    trading_name: str
    registered_name: Optional[str] = None
    discipline_code: Optional[str] = None
    provider_category: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    is_active: bool
    is_blacklisted: bool
    contracted: bool

    model_config = {"from_attributes": True}


class ProviderResponse(BaseModel):
    id: int
    practice_number: str
    registered_name: Optional[str] = None
    trading_name: str
    vat_number: Optional[str] = None
    hpcsa_number: Optional[str] = None
    sapc_number: Optional[str] = None
    dispensing_license: bool
    discipline_code: Optional[str] = None
    provider_category: Optional[str] = None
    provider_type: Optional[str] = None
    telephone: Optional[str] = None
    fax: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    contracted: bool
    is_active: bool
    is_dsp: bool
    is_blacklisted: bool
    blacklist_reason: Optional[str] = None
    blacklist_date: Optional[date] = None
    hospital_level: Optional[int] = None
    bed_count: Optional[int] = None
    icu_bed_count: Optional[int] = None
    # Banking only returned for finance_admin / super_admin
    bank_name: Optional[str] = None
    branch_code: Optional[str] = None
    account_number: Optional[str] = None
    account_type: Optional[str] = None
    account_holder: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedProvidersResponse(BaseModel):
    items: List[ProviderSummaryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DisciplineCodeResponse(BaseModel):
    id: int
    code: str
    description: str
    category: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}
