from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models.auth import User, Scheme, SchemeTheme
from app.models.reference import PlanOption
from app.auth.dependencies import get_current_user, _scheme_id_for
from app.constants import Role

router = APIRouter(prefix="/api/v1/schemes", tags=["schemes"])

VALID_PALETTES = {"sapphire", "forest", "crimson", "midnight", "plum", "teal", "amber", "indigo"}


class ThemeUpdate(BaseModel):
    palette: str


@router.get("/me")
async def get_current_scheme(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _scheme_id_for(current_user)

    result = await db.execute(select(Scheme).where(Scheme.id == sid))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    plans_result = await db.execute(
        select(PlanOption)
        .where(PlanOption.scheme_id == scheme.id)
        .order_by(PlanOption.monthly_premium)
    )
    plans = plans_result.scalars().all()

    theme_result = await db.execute(
        select(SchemeTheme).where(SchemeTheme.scheme_id == scheme.id)
    )
    theme = theme_result.scalar_one_or_none()
    palette = theme.palette if theme else "sapphire"

    return {
        "id": scheme.id,
        "name": scheme.name,
        "code": scheme.code,
        "registration_number": scheme.registration_number,
        "cms_accreditation_number": scheme.cms_accreditation_number,
        "is_active": scheme.is_active,
        "palette": palette,
        "plan_options": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "monthly_premium": p.monthly_premium,
                "is_active": p.is_active,
            }
            for p in plans
        ],
    }


@router.patch("/me/theme")
async def update_scheme_theme(
    body: ThemeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in Role.CAN_CHANGE_THEME:
        raise HTTPException(status_code=403, detail="Only scheme admins can change the theme")

    if body.palette not in VALID_PALETTES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid palette. Choose from: {', '.join(sorted(VALID_PALETTES))}",
        )

    sid = _scheme_id_for(current_user)

    theme_result = await db.execute(
        select(SchemeTheme).where(SchemeTheme.scheme_id == sid)
    )
    theme = theme_result.scalar_one_or_none()

    if theme:
        theme.palette = body.palette
    else:
        theme = SchemeTheme(scheme_id=sid, palette=body.palette)
        db.add(theme)

    await db.commit()
    return {"palette": body.palette}
