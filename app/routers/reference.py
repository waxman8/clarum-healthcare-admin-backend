"""
Reference data router — platform-wide industry codes.
All write endpoints require SUPER_ADMIN or SCHEME_ADMIN.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
import math
import csv
import io
import json

from app.database import get_db
from app.models.reference import ICD10Code, TariffCode, RejectionCode, DisciplineCode
from app.models.billing import NappiCode
from app.models.auth import User
from app.schemas.reference import (
    ICD10CodeCreate, ICD10CodeUpdate, ICD10CodeResponse, PaginatedICD10Response,
    TariffCodeCreate, TariffCodeUpdate, TariffCodeResponse, PaginatedTariffResponse,
    NappiCodeCreate, NappiCodeUpdate, NappiCodeResponse, PaginatedNappiResponse,
    RejectionCodeCreate, RejectionCodeUpdate, RejectionCodeResponse, PaginatedRejectionResponse,
    DisciplineCodeCreate, DisciplineCodeUpdate, DisciplineCodeResponse, PaginatedDisciplineResponse,
    BulkImportResult,
)
from app.auth.dependencies import get_current_user
from app.constants import Role
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/reference", tags=["reference"])

ADMIN_ROLES = [Role.SUPER_ADMIN, Role.SCHEME_ADMIN]


def _require_admin(current_user: User):
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")


# ===========================================================================
# ICD-10 Codes
# ===========================================================================

@router.get("/icd10", response_model=PaginatedICD10Response)
async def list_icd10(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_pmb: Optional[bool] = None,
    is_cdl: Optional[bool] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ICD10Code)
    if search:
        query = query.where(or_(
            ICD10Code.code.ilike(f"%{search}%"),
            ICD10Code.description.ilike(f"%{search}%"),
        ))
    if is_pmb is not None:
        query = query.where(ICD10Code.is_pmb == is_pmb)
    if is_cdl is not None:
        query = query.where(ICD10Code.is_cdl == is_cdl)
    if is_active is not None:
        query = query.where(ICD10Code.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(ICD10Code.code).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedICD10Response(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/icd10/{code_id}", response_model=ICD10CodeResponse)
async def get_icd10(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(ICD10Code).where(ICD10Code.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="ICD-10 code not found")
    return obj


@router.post("/icd10", response_model=ICD10CodeResponse, status_code=201)
async def create_icd10(
    data: ICD10CodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = (await db.execute(select(ICD10Code).where(ICD10Code.code == data.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"ICD-10 code '{data.code}' already exists")
    obj = ICD10Code(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "icd10_code", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
        new_value=json.dumps({"code": obj.code, "description": obj.description}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/icd10/{code_id}", response_model=ICD10CodeResponse)
async def update_icd10(
    code_id: int,
    data: ICD10CodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ICD10Code).where(ICD10Code.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="ICD-10 code not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "icd10_code", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/icd10/{code_id}", status_code=204)
async def delete_icd10(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(ICD10Code).where(ICD10Code.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="ICD-10 code not found")
    log_audit(
        db, "icd10_code", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
    )
    await db.delete(obj)
    await db.commit()


@router.post("/icd10/import", response_model=BulkImportResult)
async def import_icd10(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV import: columns code,description,is_pmb,is_cdl,cdl_condition_name"""
    _require_admin(current_user)
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    imported, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            code = row.get("code", "").strip().upper()
            if not code:
                errors.append(f"Row {i}: missing code")
                continue
            existing = (await db.execute(select(ICD10Code).where(ICD10Code.code == code))).scalar_one_or_none()
            if existing:
                skipped += 1
                continue
            db.add(ICD10Code(
                code=code,
                description=row.get("description", "").strip(),
                is_pmb=str(row.get("is_pmb", "")).strip().lower() in ("1", "true", "yes"),
                is_cdl=str(row.get("is_cdl", "")).strip().lower() in ("1", "true", "yes"),
                cdl_condition_name=row.get("cdl_condition_name", "").strip() or None,
            ))
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    if imported:
        log_audit(
            db, "icd10_code", None, "import_batch",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"{imported} imported, {skipped} skipped",
        )
    await db.commit()
    return BulkImportResult(imported=imported, skipped=skipped, errors=errors)


# ===========================================================================
# Tariff Codes
# ===========================================================================

@router.get("/tariffs", response_model=PaginatedTariffResponse)
async def list_tariffs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    tariff_list: Optional[str] = None,
    discipline_code: Optional[str] = None,
    requires_auth: Optional[bool] = None,
    effective_year: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(TariffCode)
    if search:
        query = query.where(or_(
            TariffCode.code.ilike(f"%{search}%"),
            TariffCode.description.ilike(f"%{search}%"),
        ))
    if tariff_list:
        query = query.where(TariffCode.tariff_list == tariff_list)
    if discipline_code:
        query = query.where(TariffCode.discipline_code == discipline_code)
    if requires_auth is not None:
        query = query.where(TariffCode.requires_auth == requires_auth)
    if effective_year is not None:
        query = query.where(TariffCode.effective_year == effective_year)
    if is_active is not None:
        query = query.where(TariffCode.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(TariffCode.code).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedTariffResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/tariffs/{code_id}", response_model=TariffCodeResponse)
async def get_tariff(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(TariffCode).where(TariffCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Tariff code not found")
    return obj


@router.post("/tariffs", response_model=TariffCodeResponse, status_code=201)
async def create_tariff(
    data: TariffCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = (await db.execute(select(TariffCode).where(TariffCode.code == data.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tariff code '{data.code}' already exists")
    obj = TariffCode(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "tariff_code", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
        new_value=json.dumps({"code": obj.code, "description": obj.description}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/tariffs/{code_id}", response_model=TariffCodeResponse)
async def update_tariff(
    code_id: int,
    data: TariffCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(TariffCode).where(TariffCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Tariff code not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "tariff_code", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/tariffs/{code_id}", status_code=204)
async def delete_tariff(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(TariffCode).where(TariffCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Tariff code not found")
    log_audit(
        db, "tariff_code", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
    )
    await db.delete(obj)
    await db.commit()


@router.post("/tariffs/import", response_model=BulkImportResult)
async def import_tariffs(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV import: columns code,description,nhrpl_rate,discipline_code,tariff_list,effective_year"""
    _require_admin(current_user)
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    imported, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            code = row.get("code", "").strip().upper()
            if not code:
                errors.append(f"Row {i}: missing code")
                continue
            existing = (await db.execute(select(TariffCode).where(TariffCode.code == code))).scalar_one_or_none()
            if existing:
                skipped += 1
                continue
            rate_str = row.get("nhrpl_rate", "0").strip().replace("R", "").replace(",", "")
            nhrpl_rate = int(float(rate_str) * 100) if "." in rate_str else int(rate_str)
            db.add(TariffCode(
                code=code,
                description=row.get("description", "").strip(),
                nhrpl_rate=nhrpl_rate,
                discipline_code=row.get("discipline_code", "").strip() or None,
                tariff_list=row.get("tariff_list", "").strip() or None,
                effective_year=int(row["effective_year"]) if row.get("effective_year", "").strip() else None,
            ))
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    if imported:
        log_audit(
            db, "tariff_code", None, "import_batch",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"{imported} imported, {skipped} skipped",
        )
    await db.commit()
    return BulkImportResult(imported=imported, skipped=skipped, errors=errors)


# ===========================================================================
# NAPPI Codes
# ===========================================================================

@router.get("/nappi", response_model=PaginatedNappiResponse)
async def list_nappi(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    schedule: Optional[str] = None,
    dosage_form: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(NappiCode)
    if search:
        query = query.where(or_(
            NappiCode.nappi_code.ilike(f"%{search}%"),
            NappiCode.product_name.ilike(f"%{search}%"),
            NappiCode.generic_name.ilike(f"%{search}%"),
        ))
    if schedule:
        query = query.where(NappiCode.schedule == schedule)
    if dosage_form:
        query = query.where(NappiCode.dosage_form.ilike(f"%{dosage_form}%"))
    if is_active is not None:
        query = query.where(NappiCode.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(NappiCode.nappi_code).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedNappiResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/nappi/{nappi_id}", response_model=NappiCodeResponse)
async def get_nappi(
    nappi_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(NappiCode).where(NappiCode.id == nappi_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="NAPPI code not found")
    return obj


@router.post("/nappi", response_model=NappiCodeResponse, status_code=201)
async def create_nappi(
    data: NappiCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = (await db.execute(select(NappiCode).where(NappiCode.nappi_code == data.nappi_code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"NAPPI code '{data.nappi_code}' already exists")
    obj = NappiCode(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "nappi_code", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.product_name or obj.nappi_code,
        new_value=json.dumps({"nappi_code": obj.nappi_code, "product_name": obj.product_name}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/nappi/{nappi_id}", response_model=NappiCodeResponse)
async def update_nappi(
    nappi_id: int,
    data: NappiCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(NappiCode).where(NappiCode.id == nappi_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="NAPPI code not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "nappi_code", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, entity_label=obj.product_name or obj.nappi_code,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/nappi/{nappi_id}", status_code=204)
async def delete_nappi(
    nappi_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(NappiCode).where(NappiCode.id == nappi_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="NAPPI code not found")
    log_audit(
        db, "nappi_code", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.product_name or obj.nappi_code,
    )
    await db.delete(obj)
    await db.commit()


@router.post("/nappi/import", response_model=BulkImportResult)
async def import_nappi(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV import: columns nappi_code,product_name,generic_name,dosage_form,strength,schedule"""
    _require_admin(current_user)
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    imported, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            nappi_code = row.get("nappi_code", "").strip()
            if not nappi_code:
                errors.append(f"Row {i}: missing nappi_code")
                continue
            existing = (await db.execute(select(NappiCode).where(NappiCode.nappi_code == nappi_code))).scalar_one_or_none()
            if existing:
                skipped += 1
                continue
            db.add(NappiCode(
                nappi_code=nappi_code,
                product_name=row.get("product_name", "").strip(),
                generic_name=row.get("generic_name", "").strip() or None,
                dosage_form=row.get("dosage_form", "").strip() or None,
                strength=row.get("strength", "").strip() or None,
                schedule=row.get("schedule", "").strip() or None,
            ))
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    if imported:
        log_audit(
            db, "nappi_code", None, "import_batch",
            user_id=current_user.id, user_role=current_user.role,
            entity_label=f"{imported} imported, {skipped} skipped",
        )
    await db.commit()
    return BulkImportResult(imported=imported, skipped=skipped, errors=errors)


# ===========================================================================
# Rejection Codes
# ===========================================================================

@router.get("/rejection-codes", response_model=PaginatedRejectionResponse)
async def list_rejection_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RejectionCode)
    if search:
        query = query.where(or_(
            RejectionCode.code.ilike(f"%{search}%"),
            RejectionCode.description.ilike(f"%{search}%"),
        ))
    if category:
        query = query.where(RejectionCode.category == category)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(RejectionCode.code).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedRejectionResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/rejection-codes/{code_id}", response_model=RejectionCodeResponse)
async def get_rejection_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(RejectionCode).where(RejectionCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Rejection code not found")
    return obj


@router.post("/rejection-codes", response_model=RejectionCodeResponse, status_code=201)
async def create_rejection_code(
    data: RejectionCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = (await db.execute(select(RejectionCode).where(RejectionCode.code == data.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rejection code '{data.code}' already exists")
    obj = RejectionCode(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "rejection_code", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
        new_value=json.dumps({"code": obj.code, "description": obj.description}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/rejection-codes/{code_id}", response_model=RejectionCodeResponse)
async def update_rejection_code(
    code_id: int,
    data: RejectionCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(RejectionCode).where(RejectionCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Rejection code not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "rejection_code", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/rejection-codes/{code_id}", status_code=204)
async def delete_rejection_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(RejectionCode).where(RejectionCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Rejection code not found")
    log_audit(
        db, "rejection_code", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
    )
    await db.delete(obj)
    await db.commit()


# ===========================================================================
# Discipline Codes
# ===========================================================================

@router.get("/discipline-codes", response_model=PaginatedDisciplineResponse)
async def list_discipline_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(DisciplineCode)
    if search:
        query = query.where(or_(
            DisciplineCode.code.ilike(f"%{search}%"),
            DisciplineCode.description.ilike(f"%{search}%"),
        ))
    if category:
        query = query.where(DisciplineCode.category == category)
    if is_active is not None:
        query = query.where(DisciplineCode.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    items = (await db.execute(
        query.order_by(DisciplineCode.code).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedDisciplineResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/discipline-codes/{code_id}", response_model=DisciplineCodeResponse)
async def get_discipline_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = (await db.execute(select(DisciplineCode).where(DisciplineCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Discipline code not found")
    return obj


@router.post("/discipline-codes", response_model=DisciplineCodeResponse, status_code=201)
async def create_discipline_code(
    data: DisciplineCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = (await db.execute(select(DisciplineCode).where(DisciplineCode.code == data.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Discipline code '{data.code}' already exists")
    obj = DisciplineCode(**data.model_dump())
    db.add(obj)
    await db.flush()
    log_audit(
        db, "discipline_code", obj.id, "create",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
        new_value=json.dumps({"code": obj.code, "description": obj.description}, default=str),
    )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.put("/discipline-codes/{code_id}", response_model=DisciplineCodeResponse)
async def update_discipline_code(
    code_id: int,
    data: DisciplineCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(DisciplineCode).where(DisciplineCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Discipline code not found")
    changes = data.model_dump(exclude_none=True)
    old_values = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    if changes:
        log_audit(
            db, "discipline_code", obj.id, "update",
            user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
            old_value=json.dumps(old_values, default=str), new_value=json.dumps(changes, default=str),
        )
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/discipline-codes/{code_id}", status_code=204)
async def delete_discipline_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    obj = (await db.execute(select(DisciplineCode).where(DisciplineCode.id == code_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Discipline code not found")
    log_audit(
        db, "discipline_code", obj.id, "delete",
        user_id=current_user.id, user_role=current_user.role, entity_label=obj.code,
    )
    await db.delete(obj)
    await db.commit()
