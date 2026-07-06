from pydantic import BaseModel
from typing import Optional, List


# ─── ICD-10 Codes ─────────────────────────────────────────────────────────────

class ICD10CodeCreate(BaseModel):
    code: str
    description: str
    is_pmb: bool = False
    is_cdl: bool = False
    cdl_condition_name: Optional[str] = None
    gender_restriction: Optional[str] = None
    is_billable: bool = True
    is_active: bool = True


class ICD10CodeUpdate(BaseModel):
    description: Optional[str] = None
    is_pmb: Optional[bool] = None
    is_cdl: Optional[bool] = None
    cdl_condition_name: Optional[str] = None
    gender_restriction: Optional[str] = None
    is_billable: Optional[bool] = None
    is_active: Optional[bool] = None


class ICD10CodeResponse(BaseModel):
    id: int
    code: str
    description: str
    is_pmb: bool
    is_cdl: bool
    cdl_condition_name: Optional[str] = None
    gender_restriction: Optional[str] = None
    is_billable: bool
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedICD10Response(BaseModel):
    items: List[ICD10CodeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Tariff Codes ─────────────────────────────────────────────────────────────

class TariffCodeCreate(BaseModel):
    code: str
    description: str
    nhrpl_rate: int  # cents
    discipline_code: Optional[str] = None
    tariff_list: Optional[str] = None
    requires_auth: bool = False
    effective_year: Optional[int] = None
    is_active: bool = True


class TariffCodeUpdate(BaseModel):
    description: Optional[str] = None
    nhrpl_rate: Optional[int] = None
    discipline_code: Optional[str] = None
    tariff_list: Optional[str] = None
    requires_auth: Optional[bool] = None
    effective_year: Optional[int] = None
    is_active: Optional[bool] = None


class TariffCodeResponse(BaseModel):
    id: int
    code: str
    description: str
    nhrpl_rate: int
    discipline_code: Optional[str] = None
    tariff_list: Optional[str] = None
    requires_auth: bool
    effective_year: Optional[int] = None
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedTariffResponse(BaseModel):
    items: List[TariffCodeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── NAPPI Codes ──────────────────────────────────────────────────────────────

class NappiCodeCreate(BaseModel):
    nappi_code: str
    product_name: str
    generic_name: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    schedule: Optional[str] = None
    is_active: bool = True


class NappiCodeUpdate(BaseModel):
    product_name: Optional[str] = None
    generic_name: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    schedule: Optional[str] = None
    is_active: Optional[bool] = None


class NappiCodeResponse(BaseModel):
    id: int
    nappi_code: str
    product_name: str
    generic_name: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    schedule: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedNappiResponse(BaseModel):
    items: List[NappiCodeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Rejection Codes ──────────────────────────────────────────────────────────

class RejectionCodeCreate(BaseModel):
    code: str
    description: str
    category: str


class RejectionCodeUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None


class RejectionCodeResponse(BaseModel):
    id: int
    code: str
    description: str
    category: str

    model_config = {"from_attributes": True}


class PaginatedRejectionResponse(BaseModel):
    items: List[RejectionCodeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Discipline Codes ─────────────────────────────────────────────────────────

class DisciplineCodeCreate(BaseModel):
    code: str
    description: str
    category: str
    is_active: bool = True


class DisciplineCodeUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class DisciplineCodeResponse(BaseModel):
    id: int
    code: str
    description: str
    category: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedDisciplineResponse(BaseModel):
    items: List[DisciplineCodeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ─── Bulk Import ──────────────────────────────────────────────────────────────

class BulkImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[str]
