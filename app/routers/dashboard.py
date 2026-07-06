from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, date
from app.database import get_db
from app.models.members import Member
from app.models.claims import Claim
from app.models.authorisations import Authorisation
from app.models.auth import User
from app.auth.dependencies import get_current_user, _effective_scheme_id

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def apply_scheme(query, model, current_user: User):
    """Scope a query to the user's scheme if they're scheme-bound."""
    sid = _effective_scheme_id(current_user)
    if sid is not None:
        query = query.where(model.scheme_id == sid)
    return query


def apply_scheme_via_member(query, current_user: User):
    """Scope authorisations to a scheme via member join."""
    sid = _effective_scheme_id(current_user)
    if sid is not None:
        query = query.join(Member, Authorisation.member_id == Member.id).where(
            Member.scheme_id == sid
        )
    return query


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _effective_scheme_id(current_user)

    # Total and active members
    total_q = select(func.count(Member.id))
    if sid:
        total_q = total_q.where(Member.scheme_id == sid)
    total_members = (await db.execute(total_q)).scalar()

    active_q = select(func.count(Member.id)).where(Member.status == "active")
    if sid:
        active_q = active_q.where(Member.scheme_id == sid)
    active_members = (await db.execute(active_q)).scalar()

    # Claims this month
    now = datetime.now()
    month_start = date(now.year, now.month, 1)

    claims_month_q = select(func.count(Claim.id)).where(Claim.date_received >= month_start)
    if sid:
        claims_month_q = claims_month_q.where(Claim.scheme_id == sid)
    total_claims_month = (await db.execute(claims_month_q)).scalar()

    # Pending claims
    pending_q = select(func.count(Claim.id)).where(Claim.status.in_(["received", "in_adjudication"]))
    if sid:
        pending_q = pending_q.where(Claim.scheme_id == sid)
    pending_claims = (await db.execute(pending_q)).scalar()

    # Total paid this month
    paid_q = select(func.sum(Claim.total_approved)).where(
        Claim.status.in_(["approved", "paid"]),
        Claim.date_received >= month_start,
    )
    if sid:
        paid_q = paid_q.where(Claim.scheme_id == sid)
    total_paid_month = (await db.execute(paid_q)).scalar() or 0

    # Open authorisations (scoped via member)
    open_auth_q = select(func.count(Authorisation.id)).where(Authorisation.status == "pending")
    if sid:
        open_auth_q = (
            select(func.count(Authorisation.id))
            .join(Member, Authorisation.member_id == Member.id)
            .where(Authorisation.status == "pending", Member.scheme_id == sid)
        )
    open_authorisations = (await db.execute(open_auth_q)).scalar()

    # Approval rate
    adj_q = select(func.count(Claim.id)).where(
        Claim.status.in_(["approved", "partial", "rejected", "paid"])
    )
    if sid:
        adj_q = adj_q.where(Claim.scheme_id == sid)
    total_adjudicated = (await db.execute(adj_q)).scalar()

    appr_q = select(func.count(Claim.id)).where(Claim.status.in_(["approved", "partial", "paid"]))
    if sid:
        appr_q = appr_q.where(Claim.scheme_id == sid)
    approved_count = (await db.execute(appr_q)).scalar()

    claims_approval_rate = (
        round(approved_count / total_adjudicated * 100, 1) if total_adjudicated > 0 else 0
    )

    # Monthly claims (last 6 months)
    monthly_data = []
    for i in range(5, -1, -1):
        if now.month - i <= 0:
            month = now.month - i + 12
            year = now.year - 1
        else:
            month = now.month - i
            year = now.year

        month_start_dt = date(year, month, 1)
        month_end_dt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        recv_q = select(func.count(Claim.id)).where(
            Claim.date_received >= month_start_dt,
            Claim.date_received < month_end_dt,
        )
        if sid:
            recv_q = recv_q.where(Claim.scheme_id == sid)
        received = (await db.execute(recv_q)).scalar()

        appr_month_q = select(func.count(Claim.id)).where(
            Claim.date_received >= month_start_dt,
            Claim.date_received < month_end_dt,
            Claim.status.in_(["approved", "partial", "paid"]),
        )
        if sid:
            appr_month_q = appr_month_q.where(Claim.scheme_id == sid)
        approved_month = (await db.execute(appr_month_q)).scalar()

        monthly_data.append({
            "month": f"{year}-{month:02d}",
            "month_label": datetime(year, month, 1).strftime("%b %Y"),
            "received": received,
            "approved": approved_month,
        })

    # Claims by status
    status_q = select(Claim.status, func.count(Claim.id)).group_by(Claim.status)
    if sid:
        status_q = status_q.where(Claim.scheme_id == sid)
    status_result = await db.execute(status_q)
    claims_by_status = [{"status": row[0], "count": row[1]} for row in status_result.fetchall()]

    # Recent claims
    recent_q = select(Claim).order_by(Claim.created_at.desc()).limit(5)
    if sid:
        recent_q = select(Claim).where(Claim.scheme_id == sid).order_by(Claim.created_at.desc()).limit(5)
    recent_claims = (await db.execute(recent_q)).scalars().all()
    recent_claims_data = [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "status": c.status,
            "total_billed": c.total_billed,
            "total_approved": c.total_approved,
            "date_received": c.date_received.isoformat(),
            "member_id": c.member_id,
        }
        for c in recent_claims
    ]

    # Pending authorisations
    if sid:
        pending_auth_q = (
            select(Authorisation)
            .join(Member, Authorisation.member_id == Member.id)
            .where(Authorisation.status == "pending", Member.scheme_id == sid)
            .limit(5)
        )
    else:
        pending_auth_q = select(Authorisation).where(Authorisation.status == "pending").limit(5)
    pending_auths = (await db.execute(pending_auth_q)).scalars().all()
    pending_auths_data = [
        {
            "id": a.id,
            "auth_number": a.auth_number,
            "auth_type": a.auth_type,
            "member_id": a.member_id,
            "created_at": a.created_at.isoformat(),
        }
        for a in pending_auths
    ]

    return {
        "total_members": total_members,
        "active_members": active_members,
        "pending_claims": pending_claims,
        "total_claims_month": total_claims_month,
        "total_paid_month": total_paid_month,
        "open_authorisations": open_authorisations,
        "claims_approval_rate": claims_approval_rate,
        "monthly_claims": monthly_data,
        "claims_by_status": claims_by_status,
        "recent_claims": recent_claims_data,
        "pending_authorisations": pending_auths_data,
    }
