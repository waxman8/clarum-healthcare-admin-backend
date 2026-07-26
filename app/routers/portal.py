from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.services.claims_statement_service import (
    generate_portal_claims_statement_pdf,
    resolve_statement_period,
)

router = APIRouter(prefix="/api/v1/portal/members", tags=["portal"])
@router.get("/me/claims-statement.pdf")
async def download_my_claims_statement_pdf(
    period_from: Optional[date] = Query(
        None,
        alias="from",
        title="Date from (YYYY-MM-DD)",
        description="Date from (YYYY-MM-DD)",
    ),
    period_to: Optional[date] = Query(
        None,
        alias="to",
        title="Date to (YYYY-MM-DD)",
        description="Date to (YYYY-MM-DD)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement_from, statement_to = resolve_statement_period(period_from, period_to)
    pdf_bytes, filename = await generate_portal_claims_statement_pdf(
        db=db,
        current_user=current_user,
        period_from=statement_from,
        period_to=statement_to,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
