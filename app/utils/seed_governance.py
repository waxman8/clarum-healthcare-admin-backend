"""
Seed script for Week-1 entities: Governance, Employers, and Intermediaries.

Seeds realistic demo data for the Demo Health Medical Scheme (DHMS).
Idempotent — checks for existing data before inserting.

Usage:
    cd backend/
    python -m app.utils.seed_governance
"""
import asyncio
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, engine, AsyncSessionLocal
from app.models.auth import Scheme
from app.models.scheme_governance import (
    Trustee, PrincipalOfficer, Administrator, ManagedCareOrganisation,
    ExternalAuditor, StatutoryActuary, ComplianceOfficer, InformationOfficer,
)
from app.models.employers import EmployerGroup
from app.models.intermediaries import (
    Brokerage, Broker, BrokerCommissionScale, BrokerAppointment,
)
from app.models.employers import MemberEmployerHistory
from app.models.members import Member


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sa_id(dob: date, gender: str) -> str:
    """Generate a valid SA ID number from date of birth and gender."""
    y = str(dob.year)[2:]
    m = f"{dob.month:02d}"
    d = f"{dob.day:02d}"
    seq = random.randint(5000, 9999) if gender == "M" else random.randint(0, 4999)
    base = f"{y}{m}{d}{seq:04d}08"
    total = sum(
        (n * 2 - 9 if n * 2 > 9 else n * 2) if i % 2 == 1 else n
        for i, n in enumerate(int(c) for c in base)
    )
    return f"{base}{(10 - total % 10) % 10}"


def _cell() -> str:
    prefix = random.choice(["071", "072", "073", "076", "082", "083"])
    return f"{prefix}{random.randint(1000000, 9999999)}"


def _email(name: str, domain: str = "demohealth.co.za") -> str:
    return f"{name.lower().replace(' ', '.')}@{domain}"


def _past_date(years_back: int = 3) -> date:
    return date.today() - timedelta(days=random.randint(30, years_back * 365))


def _future_date(years_ahead: int = 2) -> date:
    return date.today() + timedelta(days=random.randint(90, years_ahead * 365))


NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_trustees(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(Trustee).where(Trustee.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Trustees already seeded, skipping.")
        return

    trustees = [
        {
            "full_name": "Dr Nomvula Mthembu",
            "id_number": _sa_id(date(1968, 3, 15), "F"),
            "email": "n.mthembu@demohealth.co.za",
            "cell_number": _cell(),
            "role_on_board": "CHAIRPERSON",
            "appointment_date": date(2023, 1, 15),
            "term_end_date": date(2026, 12, 31),
            "vetting_status": "APPROVED",
            "vetting_date": date(2022, 11, 20),
            "conflict_disclosed": False,
            "notes": "Chairperson since Jan 2023. Former hospital CEO.",
        },
        {
            "full_name": "Advocate Sipho Ndlovu",
            "id_number": _sa_id(date(1972, 7, 22), "M"),
            "email": "s.ndlovu@demohealth.co.za",
            "cell_number": _cell(),
            "role_on_board": "DEPUTY_CHAIR",
            "appointment_date": date(2023, 1, 15),
            "term_end_date": date(2026, 12, 31),
            "vetting_status": "APPROVED",
            "vetting_date": date(2022, 11, 20),
            "conflict_disclosed": False,
        },
        {
            "full_name": "Thandi Khumalo",
            "id_number": _sa_id(date(1980, 11, 3), "F"),
            "email": "t.khumalo@demohealth.co.za",
            "cell_number": _cell(),
            "role_on_board": "MEMBER_ELECTED",
            "appointment_date": date(2024, 3, 1),
            "term_end_date": date(2027, 2, 28),
            "vetting_status": "APPROVED",
            "vetting_date": date(2024, 1, 15),
            "conflict_disclosed": True,
            "notes": "Employed by pharmacy chain — COI disclosed and managed.",
        },
        {
            "full_name": "Johan Pretorius",
            "id_number": _sa_id(date(1965, 5, 10), "M"),
            "email": "j.pretorius@demohealth.co.za",
            "cell_number": _cell(),
            "role_on_board": "MEMBER_ELECTED",
            "appointment_date": date(2024, 3, 1),
            "term_end_date": date(2027, 2, 28),
            "vetting_status": "APPROVED",
            "vetting_date": date(2024, 1, 15),
            "conflict_disclosed": False,
        },
        {
            "full_name": "Bongani Zulu",
            "id_number": _sa_id(date(1975, 9, 28), "M"),
            "email": "b.zulu@demohealth.co.za",
            "cell_number": _cell(),
            "role_on_board": "MEMBER_APPOINTED",
            "appointment_date": date(2023, 6, 1),
            "term_end_date": date(2026, 5, 31),
            "vetting_status": "APPROVED",
            "vetting_date": date(2023, 4, 10),
            "conflict_disclosed": False,
            "notes": "Independent member, appointed by CMS.",
        },
    ]

    for t in trustees:
        db.add(Trustee(scheme_id=scheme_id, created_at=NOW, updated_at=NOW, **t))
    await db.flush()
    print(f"  Seeded {len(trustees)} trustees.")


async def seed_principal_officer(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(PrincipalOfficer).where(PrincipalOfficer.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Principal Officer already seeded, skipping.")
        return

    db.add(PrincipalOfficer(
        scheme_id=scheme_id,
        full_name="Mandla Dlamini",
        id_number=_sa_id(date(1970, 6, 12), "M"),
        email="mandla.dlamini@demohealth.co.za",
        cell_number=_cell(),
        appointment_date=date(2021, 7, 1),
        cms_notification_date=date(2021, 7, 15),
        qualifications="BCom (Hons), MBA, FASSA",
        is_active=True,
        notes="Appointed by Board resolution 2021/07. CMS notified within 14 days.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 principal officer.")


async def seed_administrator(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(Administrator).where(Administrator.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Administrator already seeded, skipping.")
        return

    db.add(Administrator(
        scheme_id=scheme_id,
        company_name="Demo Health Administration Services (Pty) Ltd",
        accreditation_number="ADM/CMS/2020/042",
        accreditation_expiry=date(2027, 3, 31),
        contact_person="Liezel Botha",
        email="admin@demohealth.co.za",
        phone="0112345678",
        physical_address="15 Healthcare Drive, Sandton, Johannesburg, 2196",
        cms_accreditation_status="ACTIVE",
        contract_start_date=date(2020, 4, 1),
        contract_end_date=date(2027, 3, 31),
        notes="In-house administrator. CMS accreditation renewed 2024.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 administrator.")


async def seed_mco(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(ManagedCareOrganisation).where(ManagedCareOrganisation.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  MCOs already seeded, skipping.")
        return

    mcos = [
        {
            "company_name": "CareConnect Managed Care (Pty) Ltd",
            "accreditation_number": "MCO/CMS/2022/018",
            "accreditation_expiry": date(2027, 6, 30),
            "contact_person": "Dr Nkosi Mabaso",
            "email": "contracts@careconnect.co.za",
            "phone": "0117654321",
            "programme_types": "Chronic Disease Management, Oncology, HIV/AIDS",
            "accreditation_status": "ACTIVE",
            "contract_start_date": date(2022, 7, 1),
            "contract_end_date": date(2027, 6, 30),
        },
        {
            "company_name": "MediRisk Hospital Management (Pty) Ltd",
            "accreditation_number": "MCO/CMS/2023/007",
            "accreditation_expiry": date(2028, 1, 31),
            "contact_person": "Anna van Wyk",
            "email": "admin@medirisk.co.za",
            "phone": "0118765432",
            "programme_types": "Hospital Pre-authorisation, Case Management, DRG Review",
            "accreditation_status": "ACTIVE",
            "contract_start_date": date(2023, 2, 1),
            "contract_end_date": date(2028, 1, 31),
        },
    ]

    for m in mcos:
        db.add(ManagedCareOrganisation(scheme_id=scheme_id, created_at=NOW, updated_at=NOW, **m))
    await db.flush()
    print(f"  Seeded {len(mcos)} MCOs.")


async def seed_external_auditor(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(ExternalAuditor).where(ExternalAuditor.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  External Auditor already seeded, skipping.")
        return

    db.add(ExternalAuditor(
        scheme_id=scheme_id,
        firm_name="PricewaterhouseCoopers Inc.",
        partner_name="Pieter van der Merwe",
        irba_number="IRBA/2018/4521",
        email="pieter.vdm@pwc.co.za",
        phone="0113456789",
        appointment_date=date(2024, 1, 1),
        engagement_end_date=date(2026, 12, 31),
        is_active=True,
        notes="Appointed at AGM Nov 2023. Three-year engagement.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 external auditor.")


async def seed_statutory_actuary(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(StatutoryActuary).where(StatutoryActuary.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Statutory Actuary already seeded, skipping.")
        return

    db.add(StatutoryActuary(
        scheme_id=scheme_id,
        full_name="Dr Lwazi Ngcobo",
        firm_name="NMG Actuaries and Consultants",
        assa_fellowship_number="FASSA/2015/1287",
        email="lwazi.ngcobo@nmg.co.za",
        phone="0114567890",
        appointment_date=date(2023, 1, 1),
        term_end_date=date(2025, 12, 31),
        is_active=True,
        notes="Fellow of ASSA. Provides annual statutory actuarial reports and contribution sufficiency reviews.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 statutory actuary.")


async def seed_compliance_officer(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(ComplianceOfficer).where(ComplianceOfficer.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Compliance Officer already seeded, skipping.")
        return

    db.add(ComplianceOfficer(
        scheme_id=scheme_id,
        full_name="Zanele Mkhize",
        id_number=_sa_id(date(1978, 4, 20), "F"),
        email="zanele.mkhize@demohealth.co.za",
        cell_number=_cell(),
        appointment_date=date(2022, 3, 1),
        qualifications="LLB, Compliance Institute SA (CISA) certified",
        is_active=True,
        notes="Reports to Board Audit & Risk Committee quarterly.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 compliance officer.")


async def seed_information_officer(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(InformationOfficer).where(InformationOfficer.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Information Officer already seeded, skipping.")
        return

    db.add(InformationOfficer(
        scheme_id=scheme_id,
        full_name="Lindiwe Sithole",
        id_number=_sa_id(date(1982, 8, 14), "F"),
        email="lindiwe.sithole@demohealth.co.za",
        cell_number=_cell(),
        appointment_date=date(2021, 11, 1),
        regulator_registration_date=date(2021, 12, 15),
        is_active=True,
        notes="Registered with Information Regulator. Manages PAIA and POPIA compliance.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Seeded 1 information officer.")


async def seed_employer_groups(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(EmployerGroup).where(EmployerGroup.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Employer Groups already seeded, skipping.")
        return

    employers = [
        {
            "company_name": "Gauteng Provincial Government",
            "registration_number": "GOV/GP/001",
            "contact_person": "Maria Molefe",
            "email": "benefits@gpg.gov.za",
            "phone": "0123456789",
            "physical_address": "30 Simmonds Street, Johannesburg, 2001",
            "payroll_reference": "GPG-DHMS-001",
            "contract_start_date": date(2020, 1, 1),
            "employee_count": 2450,
            "is_active": True,
        },
        {
            "company_name": "Sasol Limited",
            "registration_number": "1979/003231/06",
            "contact_person": "Hennie du Plessis",
            "email": "employee.benefits@sasol.com",
            "phone": "0119441000",
            "physical_address": "1 Sturdee Avenue, Rosebank, 2196",
            "payroll_reference": "SASOL-DHMS-002",
            "contract_start_date": date(2021, 7, 1),
            "employee_count": 890,
            "is_active": True,
        },
        {
            "company_name": "Netcare Hospital Group",
            "registration_number": "1996/008242/06",
            "contact_person": "Sonja Brits",
            "email": "hr.benefits@netcare.co.za",
            "phone": "0117014000",
            "physical_address": "76 Maude Street, Sandton, 2196",
            "payroll_reference": "NETCARE-DHMS-003",
            "contract_start_date": date(2022, 1, 1),
            "employee_count": 560,
            "is_active": True,
        },
        {
            "company_name": "Individual Members (No Employer)",
            "contact_person": "Membership Department",
            "email": "membership@demohealth.co.za",
            "phone": "0800123456",
            "payroll_reference": "IND-DHMS",
            "contract_start_date": date(2018, 1, 1),
            "employee_count": 1200,
            "is_active": True,
            "notes": "Catch-all group for individual (non-group) members paying by debit order.",
        },
    ]

    for emp in employers:
        db.add(EmployerGroup(scheme_id=scheme_id, created_at=NOW, updated_at=NOW, **emp))
    await db.flush()
    print(f"  Seeded {len(employers)} employer groups.")


async def seed_brokerages(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(Brokerage).where(Brokerage.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Brokerages already seeded, skipping.")
        return

    brokerages = [
        {
            "company_name": "Momentum Health Solutions",
            "fsp_number": "FSP 623",
            "contact_person": "Thabo Mokoena",
            "email": "health@momentum.co.za",
            "phone": "0124278000",
            "physical_address": "268 West Avenue, Centurion, 0157",
            "fsp_status": "ACTIVE",
            "fais_category": "Health Service Benefits",
            "is_active": True,
        },
        {
            "company_name": "NMG Benefits (Pty) Ltd",
            "fsp_number": "FSP 28912",
            "contact_person": "Gerhard Joubert",
            "email": "benefits@nmg.co.za",
            "phone": "0118402000",
            "physical_address": "3rd Floor, NMG Park, 15 Eton Road, Sandhurst, 2196",
            "fsp_status": "ACTIVE",
            "fais_category": "Health Service Benefits",
            "is_active": True,
        },
        {
            "company_name": "Alexander Forbes Health",
            "fsp_number": "FSP 711",
            "contact_person": "Nomsa Radebe",
            "email": "health@alexanderforbes.co.za",
            "phone": "0112690000",
            "physical_address": "115 West Street, Sandton, 2196",
            "fsp_status": "ACTIVE",
            "fais_category": "Health Service Benefits",
            "is_active": True,
        },
    ]

    for b in brokerages:
        db.add(Brokerage(scheme_id=scheme_id, created_at=NOW, updated_at=NOW, **b))
    await db.flush()
    print(f"  Seeded {len(brokerages)} brokerages.")


async def seed_brokers(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(Broker).where(Broker.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Brokers already seeded, skipping.")
        return

    # Get brokerage IDs for linking
    result = await db.execute(select(Brokerage.id, Brokerage.company_name).where(Brokerage.scheme_id == scheme_id))
    brokerages = {row[1]: row[0] for row in result.all()}

    brokers_data = [
        {
            "full_name": "Siyanda Mabena",
            "id_number": _sa_id(date(1985, 2, 14), "M"),
            "cms_accreditation_number": "BRK/CMS/2021/1045",
            "fais_representative_number": "REP/28912/001",
            "email": "siyanda.mabena@nmg.co.za",
            "cell_number": _cell(),
            "accreditation_status": "ACTIVE",
            "accreditation_expiry": date(2026, 12, 31),
            "brokerage_name": "NMG Benefits (Pty) Ltd",
        },
        {
            "full_name": "Marie du Toit",
            "id_number": _sa_id(date(1979, 10, 5), "F"),
            "cms_accreditation_number": "BRK/CMS/2019/0782",
            "fais_representative_number": "REP/623/014",
            "email": "marie.dutoit@momentum.co.za",
            "cell_number": _cell(),
            "accreditation_status": "ACTIVE",
            "accreditation_expiry": date(2026, 12, 31),
            "brokerage_name": "Momentum Health Solutions",
        },
        {
            "full_name": "Nompumelelo Sithole",
            "id_number": _sa_id(date(1990, 6, 18), "F"),
            "cms_accreditation_number": "BRK/CMS/2023/2104",
            "fais_representative_number": "REP/711/023",
            "email": "n.sithole@alexanderforbes.co.za",
            "cell_number": _cell(),
            "accreditation_status": "ACTIVE",
            "accreditation_expiry": date(2027, 6, 30),
            "brokerage_name": "Alexander Forbes Health",
        },
        {
            "full_name": "Pieter Coetzee",
            "id_number": _sa_id(date(1975, 12, 1), "M"),
            "cms_accreditation_number": "BRK/CMS/2020/0553",
            "fais_representative_number": "REP/28912/008",
            "email": "pieter.coetzee@nmg.co.za",
            "cell_number": _cell(),
            "accreditation_status": "ACTIVE",
            "accreditation_expiry": date(2026, 12, 31),
            "brokerage_name": "NMG Benefits (Pty) Ltd",
        },
        {
            "full_name": "Thabo Moloi",
            "id_number": _sa_id(date(1988, 3, 22), "M"),
            "cms_accreditation_number": "BRK/CMS/2022/1876",
            "fais_representative_number": "REP/623/027",
            "email": "thabo.moloi@momentum.co.za",
            "cell_number": _cell(),
            "accreditation_status": "ACTIVE",
            "accreditation_expiry": date(2026, 12, 31),
            "brokerage_name": "Momentum Health Solutions",
        },
    ]

    for bd in brokers_data:
        brokerage_name = bd.pop("brokerage_name")
        brokerage_id = brokerages.get(brokerage_name)
        db.add(Broker(
            scheme_id=scheme_id,
            brokerage_id=brokerage_id,
            is_active=True,
            created_at=NOW, updated_at=NOW,
            **bd,
        ))
    await db.flush()
    print(f"  Seeded {len(brokers_data)} brokers.")


async def seed_commission_scales(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(BrokerCommissionScale).where(BrokerCommissionScale.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Commission Scales already seeded, skipping.")
        return

    # CMS Reg.28 max is R107.61 + VAT (= R123.75) per principal member per month as of 2026
    scales = [
        {"member_type": "PRINCIPAL", "commission_amount_cents": 10761, "regulatory_max_cents": 10761},
        {"member_type": "ADULT_DEPENDANT", "commission_amount_cents": 10761, "regulatory_max_cents": 10761},
        {"member_type": "CHILD_DEPENDANT", "commission_amount_cents": 5381, "regulatory_max_cents": 5381},
    ]

    for s in scales:
        db.add(BrokerCommissionScale(
            scheme_id=scheme_id,
            member_type=s["member_type"],
            commission_amount_cents=s["commission_amount_cents"],
            vat_inclusive=False,
            effective_date=date(2026, 1, 1),
            regulatory_max_cents=s["regulatory_max_cents"],
            notes="CMS Reg.28 maximum. VAT added at payment time.",
            created_at=NOW, updated_at=NOW,
        ))
    await db.flush()
    print(f"  Seeded {len(scales)} commission scale entries.")


async def seed_broker_appointments(db: AsyncSession, scheme_id: int):
    existing = await db.execute(select(BrokerAppointment).where(BrokerAppointment.scheme_id == scheme_id).limit(1))
    if existing.scalar():
        print("  Broker Appointments already seeded, skipping.")
        return

    # Get some members and brokers to link
    member_result = await db.execute(
        select(Member.id).where(Member.scheme_id == scheme_id).limit(10)
    )
    member_ids = [row[0] for row in member_result.all()]

    broker_result = await db.execute(
        select(Broker.id, Broker.brokerage_id).where(Broker.scheme_id == scheme_id)
    )
    brokers = [(row[0], row[1]) for row in broker_result.all()]

    if not member_ids or not brokers:
        print("  No members or brokers found — skipping broker appointments.")
        return

    count = 0
    for member_id in member_ids:
        broker_id, brokerage_id = random.choice(brokers)
        db.add(BrokerAppointment(
            scheme_id=scheme_id,
            member_id=member_id,
            broker_id=broker_id,
            brokerage_id=brokerage_id,
            appointment_date=_past_date(2),
            status="ACTIVE",
            created_at=NOW, updated_at=NOW,
        ))
        count += 1
    await db.flush()
    print(f"  Seeded {count} broker appointments.")


async def seed_member_employer_history(db: AsyncSession, scheme_id: int):
    existing = await db.execute(
        select(MemberEmployerHistory).where(MemberEmployerHistory.scheme_id == scheme_id).limit(1)
    )
    if existing.scalar():
        print("  Member employer history already seeded, skipping.")
        return

    # Get all DHMS members
    member_result = await db.execute(
        select(Member.id, Member.join_date).where(Member.scheme_id == scheme_id)
    )
    members = [(row[0], row[1]) for row in member_result.all()]

    # Get employer groups
    emp_result = await db.execute(
        select(EmployerGroup.id, EmployerGroup.company_name).where(EmployerGroup.scheme_id == scheme_id)
    )
    employers = {row[1]: row[0] for row in emp_result.all()}

    # Map: GPG=large gov employer, Sasol=corporate, Netcare=healthcare, Individual=catch-all
    gpg_id = employers.get("Gauteng Provincial Government")
    sasol_id = employers.get("Sasol Limited")
    netcare_id = employers.get("Netcare Hospital Group")
    individual_id = employers.get("Individual Members (No Employer)")

    if not members or not employers:
        print("  No members or employer groups found — skipping.")
        return

    # Distribute members across employers realistically:
    # - First 3 members -> GPG (gov workers)
    # - Next 3 -> Sasol (corporate)
    # - Next 2 -> Netcare (healthcare workers)
    # - Rest -> Individual (self-paying)
    employer_assignments = []
    for i, (mid, join_date) in enumerate(members):
        if i < 3 and gpg_id:
            eid = gpg_id
        elif i < 6 and sasol_id:
            eid = sasol_id
        elif i < 8 and netcare_id:
            eid = netcare_id
        elif individual_id:
            eid = individual_id
        else:
            eid = list(employers.values())[0]
        employer_assignments.append((mid, eid, join_date))

    count = 0
    for member_id, employer_group_id, join_date in employer_assignments:
        effective = join_date if join_date else date(2024, 1, 1)
        db.add(MemberEmployerHistory(
            scheme_id=scheme_id,
            member_id=member_id,
            employer_group_id=employer_group_id,
            effective_date=effective,
            end_date=None,
            employment_status="ACTIVE",
            created_at=NOW, updated_at=NOW,
        ))
        count += 1
    await db.flush()
    print(f"  Seeded {count} member-employer history records.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60)
    print("Seeding Week-1 entities for Demo Health Medical Scheme")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Find the DHMS scheme
        result = await db.execute(select(Scheme).where(Scheme.code == "DHMS"))
        scheme = result.scalar_one_or_none()

        if not scheme:
            print("ERROR: Demo Health Medical Scheme (DHMS) not found.")
            print("Run seed_demo_data.py first to create the base scheme.")
            return

        scheme_id = scheme.id
        print(f"Found scheme: {scheme.name} (id={scheme_id})")
        print()

        # Governance
        print("Governance entities:")
        await seed_trustees(db, scheme_id)
        await seed_principal_officer(db, scheme_id)
        await seed_administrator(db, scheme_id)
        await seed_mco(db, scheme_id)
        await seed_external_auditor(db, scheme_id)
        await seed_statutory_actuary(db, scheme_id)
        await seed_compliance_officer(db, scheme_id)
        await seed_information_officer(db, scheme_id)
        print()

        # Employers
        print("Employer entities:")
        await seed_employer_groups(db, scheme_id)
        print()

        # Intermediaries
        print("Intermediary entities:")
        await seed_brokerages(db, scheme_id)
        await seed_brokers(db, scheme_id)
        await seed_commission_scales(db, scheme_id)
        await seed_broker_appointments(db, scheme_id)
        print()

        # Member-Employer linkage
        print("Member-Employer linkage:")
        await seed_member_employer_history(db, scheme_id)
        print()

        await db.commit()
        print("=" * 60)
        print("Done. All Week-1 seed data committed.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
