import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback

logger = logging.getLogger("app.startup")

from app.routers import auth, members, providers, authorisations, claims, dashboard, schemes, users
from app.routers import billing, chronic, disputes, reports, reference, plan_config, underwriting
from app.routers import trustee, principal_officer, administrator_accredited
from app.routers import managed_care_organisation_mco, external_auditor, statutory_actuary
from app.routers import compliance_officer, information_officer_popia
from app.routers import employer_group, brokerage_fsp, broker_representative
from app.routers import broker_commission_scale, broker_appointment_allocation
from app.routers import member_employer_history
from app.routers import recovery_cases
# Import all models so SQLAlchemy Base.metadata and Alembic see every table
from app.models import auth as auth_models  # noqa: F401
from app.models import members as member_models  # noqa: F401
from app.models import claims as claim_models  # noqa: F401
from app.models import providers as provider_models  # noqa: F401
from app.models import reference as reference_models  # noqa: F401
from app.models import billing as billing_models  # noqa: F401
from app.models import underwriting as underwriting_models  # noqa: F401
from app.models import scheme_governance as scheme_governance_models  # noqa: F401
from app.models import employers as employer_models  # noqa: F401
from app.models import intermediaries as intermediary_models  # noqa: F401
from app.models import recovery as recovery_models  # noqa: F401

def run_migrations():
    """Run Alembic migrations synchronously."""
    import os
    from alembic.config import Config
    from alembic import command
    
    logger.info("Running Alembic migrations...")
    try:
        # Base directory is healthcare-admin-backend/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = Config(os.path.join(base_dir, "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
        
        # Synchronous call is safer for Vercel's execution model during startup
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations complete.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise e


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run migrations in a separate thread to avoid blocking the main event loop
    # and to allow asyncio.run() to work inside alembic/env.py
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_migrations)
    yield


app = FastAPI(
    title="SA Healthcare Administration Platform",
    description="SA Medical Scheme Administration System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": str(exc),
            "details": traceback.format_exc() if app.debug else None,
        },
    )


app.include_router(auth.router)
app.include_router(members.router)
app.include_router(providers.router)
app.include_router(authorisations.router)
app.include_router(claims.router)
app.include_router(dashboard.router)
app.include_router(schemes.router)
app.include_router(users.router)
app.include_router(billing.router)
app.include_router(chronic.router)
app.include_router(disputes.router)
app.include_router(reports.router)
app.include_router(reference.router)
app.include_router(plan_config.router)
app.include_router(underwriting.router)
# Week-1 sprint: Scheme Governance entities
app.include_router(trustee.router)
app.include_router(principal_officer.router)
app.include_router(administrator_accredited.router)
app.include_router(managed_care_organisation_mco.router)
app.include_router(external_auditor.router)
app.include_router(statutory_actuary.router)
app.include_router(compliance_officer.router)
app.include_router(information_officer_popia.router)
# Week-1 sprint: Employer + Intermediaries entities
app.include_router(employer_group.router)
app.include_router(brokerage_fsp.router)
app.include_router(broker_representative.router)
app.include_router(broker_commission_scale.router)
app.include_router(broker_appointment_allocation.router)
# Member-Employer link table
app.include_router(member_employer_history.router)
app.include_router(recovery_cases.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "SA Healthcare Admin API"}


@app.get("/")
async def root():
    return {"message": "SA Healthcare Administration Platform API", "docs": "/docs"}
