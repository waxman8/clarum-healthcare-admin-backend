from __future__ import annotations

from datetime import date
from html import escape
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:  # pragma: no cover - optional dependency
    Environment = None
    FileSystemLoader = None
    select_autoescape = None

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - environment-dependent optional dependency
    HTML = None

from app.auth.dependencies import _effective_scheme_id
from app.models.auth import AuditLog, User
from app.models.billing import BenefitBalance
from app.models.members import Member
from app.repositories.claim import ClaimRepository


def resolve_statement_period(period_from: Optional[date], period_to: Optional[date]) -> tuple[date, date]:
    today = date.today()
    resolved_to = period_to or today
    resolved_from = period_from or date(today.year, 1, 1)
    if resolved_from > resolved_to:
        raise HTTPException(status_code=400, detail="'from' date cannot be after 'to' date")
    return resolved_from, resolved_to


def _format_currency(cents: int | None) -> str:
    value = (cents or 0) / 100
    return f"R {value:,.2f}"


def _format_date_range(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%Y-%m-%d")
    return f"{start:%Y-%m-%d} to {end:%Y-%m-%d}"


def _clean_status(raw: str | None) -> str:
    if not raw:
        return "-"
    return raw.replace("_", " ").title()


async def _build_claims_statement_payload(
    db: AsyncSession,
    member: Member,
    period_from: date,
    period_to: date,
) -> dict[str, Any]:
    claims = await ClaimRepository(db).list_by_member_period(
        member_id=member.id,
        period_from=period_from,
        period_to=period_to,
    )

    sections_map: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if claim.dependant is None:
            section_key = "principal"
            section_title = "Principal Member"
        else:
            section_key = f"dependant:{claim.dependant.id}"
            section_title = f"Dependant: {claim.dependant.first_name} {claim.dependant.surname}"

        if section_key not in sections_map:
            sections_map[section_key] = {
                "title": section_title,
                "rows": [],
                "totals": {
                    "billed": 0,
                    "approved": 0,
                    "member_liability": 0,
                },
            }

        icd10_codes = sorted({line.icd10_code for line in claim.lines if line.icd10_code})
        tariff_codes = sorted({line.tariff_code for line in claim.lines if line.tariff_code})

        row = {
            "claim_ref": claim.claim_number,
            "date_of_service": claim.date_of_service_from.strftime("%Y-%m-%d"),
            "provider": claim.provider.trading_name if claim.provider else "-",
            "icd10": ", ".join(icd10_codes) if icd10_codes else "-",
            "tariff_codes": ", ".join(tariff_codes) if tariff_codes else "-",
            "billed": claim.total_billed or 0,
            "approved": claim.total_approved or 0,
            "member_liability": claim.total_member_liability or 0,
            "status": _clean_status(claim.status),
        }
        sections_map[section_key]["rows"].append(row)
        sections_map[section_key]["totals"]["billed"] += row["billed"]
        sections_map[section_key]["totals"]["approved"] += row["approved"]
        sections_map[section_key]["totals"]["member_liability"] += row["member_liability"]

    ordered_sections = [
        sections_map[k] for k in sorted(sections_map.keys(), key=lambda key: (0 if key == "principal" else 1, key))
    ]

    grand_totals = {"billed": 0, "approved": 0, "member_liability": 0}
    for section in ordered_sections:
        grand_totals["billed"] += section["totals"]["billed"]
        grand_totals["approved"] += section["totals"]["approved"]
        grand_totals["member_liability"] += section["totals"]["member_liability"]

    balances_result = await db.execute(
        select(BenefitBalance)
        .where(BenefitBalance.member_id == member.id)
        .where(BenefitBalance.benefit_year == period_to.year)
        .order_by(BenefitBalance.benefit_category)
    )
    balances = balances_result.scalars().all()

    return {
        "period_from": period_from,
        "period_to": period_to,
        "sections": ordered_sections,
        "grand_totals": grand_totals,
        "benefit_balances": [
            {
                "category": b.benefit_category,
                "opening": b.opening_balance_cents,
                "used": b.used_cents or 0,
                "reserved": b.reserved_cents or 0,
                "available": max(0, b.opening_balance_cents - (b.used_cents or 0) - (b.reserved_cents or 0)),
            }
            for b in balances
        ],
        "claim_count": len(claims),
    }


async def build_claims_statement_payload(
    db: AsyncSession,
    member: Member,
    period_from: date,
    period_to: date,
) -> dict[str, Any]:
    return await _build_claims_statement_payload(
        db=db,
        member=member,
        period_from=period_from,
        period_to=period_to,
    )


def _render_claims_statement_pdf(member: Member, payload: dict[str, Any]) -> bytes:
    if HTML is not None:
        html = _build_claims_statement_html(member, payload)
        try:
            return HTML(string=html).write_pdf()
        except Exception:
            pass

    return _render_claims_statement_pdf_reportlab(member, payload)


def _render_claims_statement_template(member: Member, payload: dict[str, Any]) -> Optional[str]:
    if Environment is None or FileSystemLoader is None or select_autoescape is None:
        return None

    template_root = Path(__file__).resolve().parents[1] / "templates"
    template_file = template_root / "statements" / "claims.html"
    if not template_file.exists():
        return None

    try:
        env = Environment(
            loader=FileSystemLoader(str(template_root)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("statements/claims.html")
        return template.render(
            member=member,
            payload=payload,
            period_text=f"{payload['period_from']:%Y-%m-%d} to {payload['period_to']:%Y-%m-%d}",
            format_currency=_format_currency,
        )
    except Exception:
        return None


def _build_claims_statement_html(member: Member, payload: dict[str, Any]) -> str:
    template_html = _render_claims_statement_template(member, payload)
    if template_html is not None:
        return template_html

    scheme_name = escape(member.scheme.name if member.scheme else "Scheme")
    member_name = escape(f"{member.first_name} {member.surname}")
    membership_number = escape(member.membership_number)
    id_or_passport = escape(member.id_number or member.passport_number or "-")
    period_text = f"{payload['period_from']:%Y-%m-%d} to {payload['period_to']:%Y-%m-%d}"

    section_html_parts: list[str] = []
    for section in payload["sections"]:
        rows_html = ""
        for row in section["rows"]:
            rows_html += (
                "<tr>"
                f"<td>{escape(row['claim_ref'])}</td>"
                f"<td>{escape(row['date_of_service'])}</td>"
                f"<td>{escape(row['provider'])}</td>"
                f"<td>{escape(row['icd10'])}</td>"
                f"<td>{escape(row['tariff_codes'])}</td>"
                f"<td class='num'>{_format_currency(row['billed'])}</td>"
                f"<td class='num'>{_format_currency(row['approved'])}</td>"
                f"<td class='num'>{_format_currency(row['member_liability'])}</td>"
                f"<td>{escape(row['status'])}</td>"
                "</tr>"
            )

        rows_html += (
            "<tr class='totals-row'>"
            "<td colspan='4'></td>"
            "<td>Section Total</td>"
            f"<td class='num'>{_format_currency(section['totals']['billed'])}</td>"
            f"<td class='num'>{_format_currency(section['totals']['approved'])}</td>"
            f"<td class='num'>{_format_currency(section['totals']['member_liability'])}</td>"
            "<td></td>"
            "</tr>"
        )

        section_html_parts.append(
            f"""
            <h3>{escape(section['title'])}</h3>
            <table class="claims-table">
              <thead>
                <tr>
                  <th>Claim Ref</th>
                  <th>Date of Service</th>
                  <th>Provider</th>
                  <th>ICD-10</th>
                  <th>Tariff Codes</th>
                  <th>Billed</th>
                  <th>Approved</th>
                  <th>Member Liability</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            """
        )

    no_claims_html = ""
    if not payload["sections"]:
        no_claims_html = (
            "<div style='margin-top:8px; margin-bottom:8px; padding:8px; border:1px solid #d1d5db; background:#f8fafc;'>"
            "No claims in period."
            "</div>"
        )

    grand = payload["grand_totals"]
    grand_totals_html = (
        "<table class='grand-totals'>"
        "<tr>"
        "<td class='label'>Grand Total</td>"
        f"<td class='num'>{_format_currency(grand['billed'])}</td>"
        f"<td class='num'>{_format_currency(grand['approved'])}</td>"
        f"<td class='num'>{_format_currency(grand['member_liability'])}</td>"
        "</tr>"
        "</table>"
    )

    if payload["benefit_balances"]:
        balance_rows = ""
        for b in payload["benefit_balances"]:
            balance_rows += (
                "<tr>"
                f"<td>{escape(b['category'])}</td>"
                f"<td class='num'>{_format_currency(b['opening'])}</td>"
                f"<td class='num'>{_format_currency(b['used'])}</td>"
                f"<td class='num'>{_format_currency(b['reserved'])}</td>"
                f"<td class='num'>{_format_currency(b['available'])}</td>"
                "</tr>"
            )

        balances_html = f"""
        <h3>Benefit Balance Snapshot</h3>
        <table class="balance-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Opening</th>
              <th>Used</th>
              <th>Reserved</th>
              <th>Available</th>
            </tr>
          </thead>
          <tbody>
            {balance_rows}
          </tbody>
        </table>
        """
    else:
        balances_html = "<h3>Benefit Balance Snapshot</h3><p>No benefit-balance records found for this benefit year.</p>"

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          @page {{ size: A4 landscape; margin: 15mm; }}
          body {{ font-family: Arial, sans-serif; font-size: 10px; color: #1f2937; }}
          h1 {{ font-size: 20px; margin: 0 0 2px; }}
          h2 {{ font-size: 15px; margin: 0 0 10px; }}
          h3 {{ font-size: 12px; margin: 12px 0 6px; }}
          table {{ width: 100%; border-collapse: collapse; }}
          th, td {{ border: 1px solid #d1d5db; padding: 4px 6px; vertical-align: top; }}
          thead th {{ background: #eaf2fa; font-weight: 700; text-align: left; }}
          .header-table td {{ background: #f8fafc; }}
          .claims-table {{ table-layout: fixed; }}
          .claims-table th:nth-child(1), .claims-table td:nth-child(1) {{ width: 11%; }}
          .claims-table th:nth-child(2), .claims-table td:nth-child(2) {{ width: 10%; }}
          .claims-table th:nth-child(3), .claims-table td:nth-child(3) {{ width: 18%; }}
          .claims-table th:nth-child(4), .claims-table td:nth-child(4) {{ width: 10%; }}
          .claims-table th:nth-child(5), .claims-table td:nth-child(5) {{ width: 15%; }}
          .claims-table th:nth-child(6), .claims-table td:nth-child(6) {{ width: 9%; }}
          .claims-table th:nth-child(7), .claims-table td:nth-child(7) {{ width: 9%; }}
          .claims-table th:nth-child(8), .claims-table td:nth-child(8) {{ width: 11%; }}
          .claims-table th:nth-child(9), .claims-table td:nth-child(9) {{ width: 7%; }}
          .claims-table th:nth-child(n+6),
          .claims-table td:nth-child(n+6),
          .balance-table th:nth-child(n+2),
          .balance-table td:nth-child(n+2) {{ text-align: right; }}
          .num {{ text-align: right; white-space: nowrap; }}
          .totals-row td {{ background: #f8fafc; font-weight: 700; }}
          .grand-totals {{ margin: 8px 0 12px; }}
          .grand-totals td {{ background: #d6e8f7; font-weight: 700; }}
          .grand-totals .label {{ width: 60%; text-align: left; }}
        </style>
      </head>
      <body>
        <h1>{scheme_name}</h1>
        <h2>Member Claims Statement</h2>

        <table class="header-table">
          <tbody>
            <tr>
              <td><b>Member Name</b></td>
              <td>{member_name}</td>
              <td><b>Membership No.</b></td>
              <td>{membership_number}</td>
            </tr>
            <tr>
              <td><b>ID / Passport</b></td>
              <td>{id_or_passport}</td>
              <td><b>Statement Period</b></td>
              <td>{period_text}</td>
            </tr>
          </tbody>
        </table>

        {''.join(section_html_parts)}
                {no_claims_html}
        {grand_totals_html}
        {balances_html}
      </body>
    </html>
    """


def _render_claims_statement_pdf_reportlab(member: Member, payload: dict[str, Any]) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Member Claims Statement",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=10.5))
    styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading3"], fontSize=11, spaceAfter=6))

    story = []
    scheme_name = member.scheme.name if member.scheme else "Scheme"
    story.append(Paragraph(f"<b>{scheme_name}</b>", styles["Title"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Member Claims Statement", styles["Heading2"]))
    story.append(Spacer(1, 8))

    header_data = [
        ["Member Name", f"{member.first_name} {member.surname}", "Membership No.", member.membership_number],
        [
            "ID / Passport",
            member.id_number or member.passport_number or "-",
            "Statement Period",
            f"{payload['period_from']:%Y-%m-%d} to {payload['period_to']:%Y-%m-%d}",
        ],
    ]
    header_table = Table(header_data, colWidths=[95, 230, 95, 230])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 10))

    col_widths = [96, 70, 135, 80, 110, 75, 75, 85, 65]
    columns = [
        "Claim Ref",
        "Date",
        "Provider",
        "ICD-10",
        "Tariff Codes",
        "Billed (R)",
        "Approved",
        "Liability (R)",
        "Status",
    ]

    for section in payload["sections"]:
        story.append(Paragraph(section["title"], styles["SectionTitle"]))
        rows = [columns]
        for row in section["rows"]:
            rows.append(
                [
                    row["claim_ref"],
                    row["date_of_service"],
                    Paragraph(row["provider"], styles["Small"]),
                    Paragraph(row["icd10"], styles["Small"]),
                    Paragraph(row["tariff_codes"], styles["Small"]),
                    _format_currency(row["billed"]),
                    _format_currency(row["approved"]),
                    _format_currency(row["member_liability"]),
                    row["status"],
                ]
            )

        rows.append(
            [
                "",
                "",
                "",
                "",
                "Section Total",
                _format_currency(section["totals"]["billed"]),
                _format_currency(section["totals"]["approved"]),
                _format_currency(section["totals"]["member_liability"]),
                "",
            ]
        )
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FA")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("ALIGN", (5, 1), (7, -1), "RIGHT"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                    ("FONTNAME", (4, -1), (7, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))

    if not payload["sections"]:
        story.append(Paragraph("No claims in period.", styles["Small"]))
        story.append(Spacer(1, 6))

    grand = payload["grand_totals"]
    grand_table = Table(
        [["Grand Total", _format_currency(grand["billed"]), _format_currency(grand["approved"]), _format_currency(grand["member_liability"])]],
        colWidths=[475, 107, 107, 108],
    )
    grand_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#D6E8F7")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ]
        )
    )
    story.append(grand_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Benefit Balance Snapshot", styles["Heading3"]))
    if payload["benefit_balances"]:
        balance_rows = [["Category", "Opening", "Used", "Reserved", "Available"]]
        for b in payload["benefit_balances"]:
            balance_rows.append(
                [
                    b["category"],
                    _format_currency(b["opening"]),
                    _format_currency(b["used"]),
                    _format_currency(b["reserved"]),
                    _format_currency(b["available"]),
                ]
            )

        balance_table = Table(balance_rows, colWidths=[317, 120, 120, 120, 120], repeatRows=1)
        balance_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F6F8")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]
            )
        )
        story.append(balance_table)
    else:
        story.append(Paragraph("No benefit-balance records found for this benefit year.", styles["Small"]))

    doc.build(story)
    return buffer.getvalue()


async def generate_staff_claims_statement_pdf(
    db: AsyncSession,
    current_user: User,
    member_id: int,
    period_from: date,
    period_to: date,
) -> tuple[bytes, str]:
    sid = _effective_scheme_id(current_user)
    member_query = select(Member).where(Member.id == member_id).options(selectinload(Member.scheme))
    if sid is not None:
        member_query = member_query.where(Member.scheme_id == sid)

    member_result = await db.execute(member_query)
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    payload = await _build_claims_statement_payload(
        db=db,
        member=member,
        period_from=period_from,
        period_to=period_to,
    )
    pdf_bytes = _render_claims_statement_pdf(member, payload)

    db.add(
        AuditLog(
            user_id=current_user.id,
            entity_type="member_claims_statement",
            entity_id=member.id,
            action="download_pdf",
            new_value=json.dumps(
                {
                    "from": period_from.isoformat(),
                    "to": period_to.isoformat(),
                    "claim_count": payload["claim_count"],
                    "scope": "staff",
                }
            ),
        )
    )
    await db.commit()

    filename = (
        f"claims-statement-{member.membership_number}-"
        f"{period_from:%Y%m%d}-{period_to:%Y%m%d}.pdf"
    )
    return pdf_bytes, filename


async def generate_portal_claims_statement_pdf(
    db: AsyncSession,
    current_user: User,
    period_from: date,
    period_to: date,
) -> tuple[bytes, str]:
    sid = _effective_scheme_id(current_user)
    member_query = select(Member).options(selectinload(Member.scheme))

    # Portal statements are restricted to the caller's own member record.
    # Enforce user-to-member linkage via email, and optionally also JWT member_id when present.
    member_query = member_query.where(Member.email == current_user.email)
    session_member_id = getattr(current_user, "_session_member_id", None)
    if session_member_id is not None:
        member_query = member_query.where(Member.id == session_member_id)

    if sid is not None:
        member_query = member_query.where(Member.scheme_id == sid)

    member_result = await db.execute(member_query)
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Portal member record not found")

    payload = await _build_claims_statement_payload(
        db=db,
        member=member,
        period_from=period_from,
        period_to=period_to,
    )
    pdf_bytes = _render_claims_statement_pdf(member, payload)

    db.add(
        AuditLog(
            user_id=current_user.id,
            entity_type="member_claims_statement",
            entity_id=member.id,
            action="download_pdf",
            new_value=json.dumps(
                {
                    "from": period_from.isoformat(),
                    "to": period_to.isoformat(),
                    "claim_count": payload["claim_count"],
                    "scope": "portal_self",
                }
            ),
        )
    )
    await db.commit()

    filename = (
        f"claims-statement-{member.membership_number}-"
        f"{period_from:%Y%m%d}-{period_to:%Y%m%d}.pdf"
    )
    return pdf_bytes, filename
