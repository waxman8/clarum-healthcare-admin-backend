"""
Comprehensive seed for MDV Health Medical Scheme (MDVH).

Seeds all Week-1 entities (governance, employers, intermediaries, member-employer
history) plus chronic registrations, disputes, copayment rules, provider networks,
and underwriting decisions.

Idempotent — checks for existing data per category before inserting.

Usage:
    cd backend/
    python -m app.utils.seed_mdvh_complete
"""
import asyncio
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.auth import Scheme
from app.models.members import Member
from app.models.reference import PlanOption, ICD10Code
from app.models.providers import Provider
from app.models.billing import (
    CopaymentRule, ProviderNetwork, ChronicRegistration, Dispute,
)
from app.models.underwriting import UnderwritingDecision
from app.models.scheme_governance import (
    Trustee, PrincipalOfficer, Administrator, ManagedCareOrganisation,
    ExternalAuditor, StatutoryActuary, ComplianceOfficer, InformationOfficer,
)
from app.models.employers import EmployerGroup, MemberEmployerHistory
from app.models.intermediaries import (
    Brokerage, Broker, BrokerCommissionScale, BrokerAppointment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def _sa_id(dob: date, gender: str) -> str:
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
    return f"{random.choice(['071','072','076','082','083'])}{random.randint(1000000, 9999999)}"


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

async def seed_trustees(db: AsyncSession, sid: int):
    if (await db.execute(select(Trustee).where(Trustee.scheme_id == sid).limit(1))).scalar():
        print("  Trustees: already seeded")
        return
    data = [
        {"full_name": "Adv. Kgomotso Sefatsa", "id_number": _sa_id(date(1966, 8, 12), "F"),
         "email": "k.sefatsa@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "CHAIRPERSON", "appointment_date": date(2022, 7, 1),
         "term_end_date": date(2025, 6, 30), "vetting_status": "APPROVED",
         "vetting_date": date(2022, 5, 15), "conflict_disclosed": False,
         "notes": "Chairperson. Former Chamber of Mines legal counsel."},
        {"full_name": "Danie Swanepoel", "id_number": _sa_id(date(1970, 3, 22), "M"),
         "email": "d.swanepoel@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "DEPUTY_CHAIR", "appointment_date": date(2022, 7, 1),
         "term_end_date": date(2025, 6, 30), "vetting_status": "APPROVED",
         "vetting_date": date(2022, 5, 15), "conflict_disclosed": False,
         "notes": "Deputy chair. HR Director at Anglo American Platinum."},
        {"full_name": "Sibusiso Hadebe", "id_number": _sa_id(date(1978, 11, 5), "M"),
         "email": "s.hadebe@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "MEMBER_ELECTED", "appointment_date": date(2024, 1, 1),
         "term_end_date": date(2026, 12, 31), "vetting_status": "APPROVED",
         "vetting_date": date(2023, 11, 10), "conflict_disclosed": False,
         "notes": "Elected by members. Shift supervisor at Impala Platinum."},
        {"full_name": "Elsa Kruger", "id_number": _sa_id(date(1974, 6, 18), "F"),
         "email": "e.kruger@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "MEMBER_ELECTED", "appointment_date": date(2024, 1, 1),
         "term_end_date": date(2026, 12, 31), "vetting_status": "APPROVED",
         "vetting_date": date(2023, 11, 10), "conflict_disclosed": True,
         "notes": "Elected by members. Employed by Medipost pharmacy — COI disclosed."},
        {"full_name": "Trevor Moodley", "id_number": _sa_id(date(1969, 1, 30), "M"),
         "email": "t.moodley@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "MEMBER_APPOINTED", "appointment_date": date(2023, 4, 1),
         "term_end_date": date(2026, 3, 31), "vetting_status": "APPROVED",
         "vetting_date": date(2023, 2, 20), "conflict_disclosed": False,
         "notes": "Independent appointee. Chartered accountant, former CMS reviewer."},
        {"full_name": "Nhlanhla Ngwenya", "id_number": _sa_id(date(1982, 4, 9), "M"),
         "email": "n.ngwenya@mdvhealth.co.za", "cell_number": _cell(),
         "role_on_board": "MEMBER_APPOINTED", "appointment_date": date(2023, 4, 1),
         "term_end_date": date(2026, 3, 31), "vetting_status": "APPROVED",
         "vetting_date": date(2023, 2, 20), "conflict_disclosed": False,
         "notes": "Nominated by employer consortium. Occupational health manager, Sibanye-Stillwater."},
    ]
    for t in data:
        db.add(Trustee(scheme_id=sid, created_at=NOW, updated_at=NOW, **t))
    await db.flush()
    print(f"  Trustees: seeded {len(data)}")


async def seed_principal_officer(db: AsyncSession, sid: int):
    if (await db.execute(select(PrincipalOfficer).where(PrincipalOfficer.scheme_id == sid).limit(1))).scalar():
        print("  Principal Officer: already seeded")
        return
    db.add(PrincipalOfficer(
        scheme_id=sid, full_name="Kobus Lombard",
        id_number=_sa_id(date(1967, 9, 14), "M"),
        email="kobus.lombard@mdvhealth.co.za", cell_number=_cell(),
        appointment_date=date(2020, 1, 1),
        cms_notification_date=date(2020, 1, 10),
        qualifications="BCom (Hons), CIA, FIIASA",
        is_active=True,
        notes="Appointed by Board. 25 years mining-sector employee benefits experience.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Principal Officer: seeded 1")


async def seed_administrator(db: AsyncSession, sid: int):
    if (await db.execute(select(Administrator).where(Administrator.scheme_id == sid).limit(1))).scalar():
        print("  Administrator: already seeded")
        return
    db.add(Administrator(
        scheme_id=sid,
        company_name="MDV Health Administration Services (Pty) Ltd",
        accreditation_number="ADM/CMS/2019/028",
        accreditation_expiry=date(2027, 12, 31),
        contact_person="Ansie Marais",
        email="admin@mdvhealth.co.za", phone="0145251000",
        physical_address="22 Fatima Bhayat Street, Rustenburg, 0300",
        cms_accreditation_status="ACTIVE",
        contract_start_date=date(2019, 1, 1),
        contract_end_date=date(2027, 12, 31),
        notes="In-house administrator. Rustenburg head office.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Administrator: seeded 1")


async def seed_mcos(db: AsyncSession, sid: int):
    if (await db.execute(select(ManagedCareOrganisation).where(ManagedCareOrganisation.scheme_id == sid).limit(1))).scalar():
        print("  MCOs: already seeded")
        return
    data = [
        {"company_name": "MineHealth Managed Care (Pty) Ltd",
         "accreditation_number": "MCO/CMS/2021/031",
         "accreditation_expiry": date(2026, 12, 31),
         "contact_person": "Dr Vusi Sibiya",
         "email": "contracts@minehealth.co.za", "phone": "0127654321",
         "programme_types": "Occupational Disease Management, HIV/AIDS/TB, Chronic Disease Management",
         "accreditation_status": "ACTIVE",
         "contract_start_date": date(2021, 1, 1),
         "contract_end_date": date(2026, 12, 31)},
        {"company_name": "Platinum Health Solutions (Pty) Ltd",
         "accreditation_number": "MCO/CMS/2023/012",
         "accreditation_expiry": date(2028, 6, 30),
         "contact_person": "Leon Joubert",
         "email": "managed@platinumhealth.co.za", "phone": "0145552233",
         "programme_types": "Hospital Pre-authorisation, Case Management, Trauma Management",
         "accreditation_status": "ACTIVE",
         "contract_start_date": date(2023, 7, 1),
         "contract_end_date": date(2028, 6, 30)},
    ]
    for m in data:
        db.add(ManagedCareOrganisation(scheme_id=sid, created_at=NOW, updated_at=NOW, **m))
    await db.flush()
    print(f"  MCOs: seeded {len(data)}")


async def seed_external_auditor(db: AsyncSession, sid: int):
    if (await db.execute(select(ExternalAuditor).where(ExternalAuditor.scheme_id == sid).limit(1))).scalar():
        print("  External Auditor: already seeded")
        return
    db.add(ExternalAuditor(
        scheme_id=sid,
        firm_name="Deloitte & Touche",
        partner_name="Ansie van Rensburg",
        irba_number="IRBA/2019/3842",
        email="avanrensburg@deloitte.co.za", phone="0124827000",
        appointment_date=date(2024, 7, 1),
        engagement_end_date=date(2027, 6, 30),
        is_active=True,
        notes="Three-year engagement. Appointed at 2024 AGM.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  External Auditor: seeded 1")


async def seed_statutory_actuary(db: AsyncSession, sid: int):
    if (await db.execute(select(StatutoryActuary).where(StatutoryActuary.scheme_id == sid).limit(1))).scalar():
        print("  Statutory Actuary: already seeded")
        return
    db.add(StatutoryActuary(
        scheme_id=sid,
        full_name="Gerhard Erasmus",
        firm_name="Towers Watson Actuarial Advisory",
        assa_fellowship_number="FASSA/2012/0943",
        email="gerhard.erasmus@towerswatson.co.za", phone="0113876000",
        appointment_date=date(2022, 1, 1),
        term_end_date=date(2026, 12, 31),
        is_active=True,
        notes="Fellow of ASSA. Mining-sector benefits specialist. Annual statutory reports and contribution adequacy reviews.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Statutory Actuary: seeded 1")


async def seed_compliance_officer(db: AsyncSession, sid: int):
    if (await db.execute(select(ComplianceOfficer).where(ComplianceOfficer.scheme_id == sid).limit(1))).scalar():
        print("  Compliance Officer: already seeded")
        return
    db.add(ComplianceOfficer(
        scheme_id=sid,
        full_name="Phindile Ntanzi",
        id_number=_sa_id(date(1981, 7, 25), "F"),
        email="phindile.ntanzi@mdvhealth.co.za", cell_number=_cell(),
        appointment_date=date(2021, 6, 1),
        qualifications="LLB, Compliance Institute SA (CISA), Mine Health & Safety Act certified",
        is_active=True,
        notes="Reports to Board Audit & Risk Committee. Also manages MHSA compliance overlap.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Compliance Officer: seeded 1")


async def seed_information_officer(db: AsyncSession, sid: int):
    if (await db.execute(select(InformationOfficer).where(InformationOfficer.scheme_id == sid).limit(1))).scalar():
        print("  Information Officer: already seeded")
        return
    db.add(InformationOfficer(
        scheme_id=sid,
        full_name="Cindy Fernandez",
        id_number=_sa_id(date(1984, 2, 11), "F"),
        email="cindy.fernandez@mdvhealth.co.za", cell_number=_cell(),
        appointment_date=date(2022, 4, 1),
        regulator_registration_date=date(2022, 5, 20),
        is_active=True,
        notes="Registered with Information Regulator. PAIA/POPIA compliance for scheme and occupational health records.",
        created_at=NOW, updated_at=NOW,
    ))
    await db.flush()
    print("  Information Officer: seeded 1")


# ---------------------------------------------------------------------------
# Employers
# ---------------------------------------------------------------------------

async def seed_employer_groups(db: AsyncSession, sid: int):
    if (await db.execute(select(EmployerGroup).where(EmployerGroup.scheme_id == sid).limit(1))).scalar():
        print("  Employer Groups: already seeded")
        return
    data = [
        {"company_name": "Anglo American Platinum Ltd",
         "registration_number": "1946/022452/06",
         "contact_person": "Nhlanhla Ngwenya",
         "email": "benefits@angloplat.com", "phone": "0114841700",
         "physical_address": "55 Marshall Street, Johannesburg, 2001",
         "payroll_reference": "AMPLAT-MDVH-001",
         "contract_start_date": date(2019, 1, 1), "employee_count": 3200, "is_active": True,
         "notes": "Founding employer group. Rustenburg and Mogalakwena operations."},
        {"company_name": "Sibanye-Stillwater Operations Ltd",
         "registration_number": "2014/243998/06",
         "contact_person": "Mbuso Cele",
         "email": "hr.benefits@sibanyestillwater.com", "phone": "0112784700",
         "physical_address": "Constantia Office Park, Bridgeview House, Roodepoort",
         "payroll_reference": "SSW-MDVH-002",
         "contract_start_date": date(2020, 7, 1), "employee_count": 2800, "is_active": True,
         "notes": "PGM and gold operations. Marikana and Driefontein sites."},
        {"company_name": "Royal Bafokeng Platinum",
         "registration_number": "2008/015696/06",
         "contact_person": "Tshepo Maluleka",
         "email": "benefits@bafokengplatinum.co.za", "phone": "0145251500",
         "physical_address": "The Pivot, Block C, Montecasino Boulevard, Fourways",
         "payroll_reference": "RBP-MDVH-003",
         "contract_start_date": date(2021, 1, 1), "employee_count": 1500, "is_active": True,
         "notes": "BRPM and Styldrift operations."},
        {"company_name": "Rustenburg Municipal Workers",
         "registration_number": "GOV/NW/RUST/001",
         "contact_person": "Oratile Sekhwela",
         "email": "hr@rustenburg.gov.za", "phone": "0145291111",
         "physical_address": "Cnr Beyers Naude & Nelson Mandela, Rustenburg, 0300",
         "payroll_reference": "RUST-MDVH-004",
         "contract_start_date": date(2022, 1, 1), "employee_count": 450, "is_active": True,
         "notes": "Municipal employees and councillors."},
        {"company_name": "Individual Members (Self-Paying)",
         "contact_person": "Membership Department",
         "email": "membership@mdvhealth.co.za", "phone": "0800654321",
         "payroll_reference": "IND-MDVH",
         "contract_start_date": date(2019, 1, 1), "employee_count": 600, "is_active": True,
         "notes": "Continuation members, retirees, and self-paying individuals."},
    ]
    for e in data:
        db.add(EmployerGroup(scheme_id=sid, created_at=NOW, updated_at=NOW, **e))
    await db.flush()
    print(f"  Employer Groups: seeded {len(data)}")


async def seed_member_employer_history(db: AsyncSession, sid: int):
    if (await db.execute(select(MemberEmployerHistory).where(MemberEmployerHistory.scheme_id == sid).limit(1))).scalar():
        print("  Member-Employer History: already seeded")
        return

    members = (await db.execute(
        select(Member.id, Member.join_date).where(Member.scheme_id == sid).limit(50)
    )).all()

    employers = (await db.execute(
        select(EmployerGroup.id, EmployerGroup.company_name).where(EmployerGroup.scheme_id == sid)
    )).all()
    emp_map = {row[1]: row[0] for row in employers}

    anglo_id = emp_map.get("Anglo American Platinum Ltd")
    sibanye_id = emp_map.get("Sibanye-Stillwater Operations Ltd")
    rbp_id = emp_map.get("Royal Bafokeng Platinum")
    muni_id = emp_map.get("Rustenburg Municipal Workers")
    ind_id = emp_map.get("Individual Members (Self-Paying)")

    if not members or not employers:
        print("  No members or employers — skipping")
        return

    count = 0
    for i, (mid, join_date) in enumerate(members):
        # Weighted distribution reflecting mining sector dominance
        if i % 10 < 3:
            eid = anglo_id
        elif i % 10 < 6:
            eid = sibanye_id
        elif i % 10 < 8:
            eid = rbp_id
        elif i % 10 == 8:
            eid = muni_id
        else:
            eid = ind_id

        effective = join_date if join_date else date(2024, 1, 1)
        db.add(MemberEmployerHistory(
            scheme_id=sid, member_id=mid, employer_group_id=eid,
            effective_date=effective, end_date=None, employment_status="ACTIVE",
            created_at=NOW, updated_at=NOW,
        ))
        count += 1
    await db.flush()
    print(f"  Member-Employer History: seeded {count}")


# ---------------------------------------------------------------------------
# Intermediaries
# ---------------------------------------------------------------------------

async def seed_brokerages(db: AsyncSession, sid: int):
    if (await db.execute(select(Brokerage).where(Brokerage.scheme_id == sid).limit(1))).scalar():
        print("  Brokerages: already seeded")
        return
    data = [
        {"company_name": "FedGroup Employee Benefits",
         "fsp_number": "FSP 856",
         "contact_person": "Byron Adendorff",
         "email": "benefits@fedgroup.co.za", "phone": "0118091200",
         "physical_address": "3rd Floor, Building 2, Greenstone Hill, Edenvale",
         "fsp_status": "ACTIVE", "fais_category": "Health Service Benefits", "is_active": True},
        {"company_name": "Xelus Employee Benefits",
         "fsp_number": "FSP 14805",
         "contact_person": "Shane Govender",
         "email": "health@xelus.co.za", "phone": "0118050600",
         "physical_address": "Block C, Pinmill Farm, 164 Katherine Street, Sandton",
         "fsp_status": "ACTIVE", "fais_category": "Health Service Benefits", "is_active": True},
        {"company_name": "Platinum Financial Services",
         "fsp_number": "FSP 31245",
         "contact_person": "Leon Myburgh",
         "email": "health@platfin.co.za", "phone": "0145256700",
         "physical_address": "18 Kerk Street, Rustenburg, 0300",
         "fsp_status": "ACTIVE", "fais_category": "Health Service Benefits", "is_active": True,
         "notes": "Local Rustenburg brokerage specialising in mining-sector schemes."},
    ]
    for b in data:
        db.add(Brokerage(scheme_id=sid, created_at=NOW, updated_at=NOW, **b))
    await db.flush()
    print(f"  Brokerages: seeded {len(data)}")


async def seed_brokers(db: AsyncSession, sid: int):
    if (await db.execute(select(Broker).where(Broker.scheme_id == sid).limit(1))).scalar():
        print("  Brokers: already seeded")
        return

    brokerages = {row[1]: row[0] for row in (await db.execute(
        select(Brokerage.id, Brokerage.company_name).where(Brokerage.scheme_id == sid)
    )).all()}

    data = [
        {"full_name": "Byron Adendorff", "id_number": _sa_id(date(1980, 5, 3), "M"),
         "cms_accreditation_number": "BRK/CMS/2018/0623",
         "fais_representative_number": "REP/856/001",
         "email": "byron@fedgroup.co.za", "cell_number": _cell(),
         "accreditation_status": "ACTIVE", "accreditation_expiry": date(2027, 3, 31),
         "brokerage": "FedGroup Employee Benefits"},
        {"full_name": "Vanessa Chetty", "id_number": _sa_id(date(1986, 8, 19), "F"),
         "cms_accreditation_number": "BRK/CMS/2020/1178",
         "fais_representative_number": "REP/856/009",
         "email": "vanessa@fedgroup.co.za", "cell_number": _cell(),
         "accreditation_status": "ACTIVE", "accreditation_expiry": date(2027, 3, 31),
         "brokerage": "FedGroup Employee Benefits"},
        {"full_name": "Shane Govender", "id_number": _sa_id(date(1977, 12, 1), "M"),
         "cms_accreditation_number": "BRK/CMS/2017/0421",
         "fais_representative_number": "REP/14805/001",
         "email": "shane@xelus.co.za", "cell_number": _cell(),
         "accreditation_status": "ACTIVE", "accreditation_expiry": date(2026, 12, 31),
         "brokerage": "Xelus Employee Benefits"},
        {"full_name": "Leon Myburgh", "id_number": _sa_id(date(1972, 3, 15), "M"),
         "cms_accreditation_number": "BRK/CMS/2019/0834",
         "fais_representative_number": "REP/31245/001",
         "email": "leon@platfin.co.za", "cell_number": _cell(),
         "accreditation_status": "ACTIVE", "accreditation_expiry": date(2027, 6, 30),
         "brokerage": "Platinum Financial Services"},
        {"full_name": "Palesa Sefatsa", "id_number": _sa_id(date(1991, 6, 28), "F"),
         "cms_accreditation_number": "BRK/CMS/2023/2456",
         "fais_representative_number": "REP/31245/003",
         "email": "palesa@platfin.co.za", "cell_number": _cell(),
         "accreditation_status": "ACTIVE", "accreditation_expiry": date(2027, 6, 30),
         "brokerage": "Platinum Financial Services"},
    ]
    for bd in data:
        brokerage_name = bd.pop("brokerage")
        db.add(Broker(
            scheme_id=sid, brokerage_id=brokerages.get(brokerage_name),
            is_active=True, created_at=NOW, updated_at=NOW, **bd,
        ))
    await db.flush()
    print(f"  Brokers: seeded {len(data)}")


async def seed_commission_scales(db: AsyncSession, sid: int):
    if (await db.execute(select(BrokerCommissionScale).where(BrokerCommissionScale.scheme_id == sid).limit(1))).scalar():
        print("  Commission Scales: already seeded")
        return
    scales = [
        {"member_type": "PRINCIPAL", "commission_amount_cents": 10761, "regulatory_max_cents": 10761},
        {"member_type": "ADULT_DEPENDANT", "commission_amount_cents": 10761, "regulatory_max_cents": 10761},
        {"member_type": "CHILD_DEPENDANT", "commission_amount_cents": 5381, "regulatory_max_cents": 5381},
    ]
    for s in scales:
        db.add(BrokerCommissionScale(
            scheme_id=sid, vat_inclusive=False, effective_date=date(2026, 1, 1),
            notes="CMS Reg.28 maximum for 2026.", created_at=NOW, updated_at=NOW, **s,
        ))
    await db.flush()
    print(f"  Commission Scales: seeded {len(scales)}")


async def seed_broker_appointments(db: AsyncSession, sid: int):
    if (await db.execute(select(BrokerAppointment).where(BrokerAppointment.scheme_id == sid).limit(1))).scalar():
        print("  Broker Appointments: already seeded")
        return

    members = [row[0] for row in (await db.execute(
        select(Member.id).where(Member.scheme_id == sid).limit(30)
    )).all()]

    brokers = [(row[0], row[1]) for row in (await db.execute(
        select(Broker.id, Broker.brokerage_id).where(Broker.scheme_id == sid)
    )).all()]

    if not members or not brokers:
        print("  No members or brokers — skipping")
        return

    count = 0
    for mid in members:
        broker_id, brokerage_id = random.choice(brokers)
        db.add(BrokerAppointment(
            scheme_id=sid, member_id=mid, broker_id=broker_id, brokerage_id=brokerage_id,
            appointment_date=date(2024, 1, 1) + timedelta(days=random.randint(0, 500)),
            status="ACTIVE", created_at=NOW, updated_at=NOW,
        ))
        count += 1
    await db.flush()
    print(f"  Broker Appointments: seeded {count}")


# ---------------------------------------------------------------------------
# Copayment Rules
# ---------------------------------------------------------------------------

async def seed_copayment_rules(db: AsyncSession, sid: int):
    if (await db.execute(select(CopaymentRule).where(CopaymentRule.scheme_id == sid).limit(1))).scalar():
        print("  Copayment Rules: already seeded")
        return

    plans = {row[1]: row[0] for row in (await db.execute(
        select(PlanOption.id, PlanOption.code).where(PlanOption.scheme_id == sid)
    )).all()}

    # CopaymentRule columns: trigger, copayment_type (PERCENTAGE|RAND_AMOUNT), copayment_value, description, is_upfront, is_active
    rules = [
        {"trigger": "NON_NETWORK_GP", "copayment_type": "RAND_AMOUNT",
         "copayment_value": 15000, "description": "R150 co-pay for non-network GP visit",
         "is_upfront": True, "is_active": True},
        {"trigger": "ER_NOT_ADMITTED", "copayment_type": "RAND_AMOUNT",
         "copayment_value": 35000, "description": "R350 ER co-pay if not admitted",
         "is_upfront": True, "is_active": True},
        {"trigger": "NON_FORMULARY_CHRONIC", "copayment_type": "PERCENTAGE",
         "copayment_value": 2000, "description": "20% co-pay for non-formulary chronic medicine",
         "is_upfront": False, "is_active": True},
        {"trigger": "SPECIALIST_NO_REFERRAL", "copayment_type": "RAND_AMOUNT",
         "copayment_value": 30000, "description": "R300 co-pay for self-referred specialist (Core only)",
         "is_upfront": True, "is_active": True,
         "plan_option_id": plans.get("CORE")},
        {"trigger": "ADVANCED_RADIOLOGY", "copayment_type": "PERCENTAGE",
         "copayment_value": 2500, "description": "25% co-pay for MRI/CT on Core plan",
         "is_upfront": False, "is_active": True,
         "plan_option_id": plans.get("CORE")},
    ]
    for r in rules:
        db.add(CopaymentRule(scheme_id=sid, **r))
    await db.flush()
    print(f"  Copayment Rules: seeded {len(rules)}")


# ---------------------------------------------------------------------------
# Provider Networks
# ---------------------------------------------------------------------------

async def seed_provider_networks(db: AsyncSession, sid: int):
    if (await db.execute(select(ProviderNetwork).where(ProviderNetwork.scheme_id == sid).limit(1))).scalar():
        print("  Provider Networks: already seeded")
        return

    providers = [row[0] for row in (await db.execute(select(Provider.id).limit(10))).all()]

    if not providers:
        print("  No providers — skipping")
        return

    # ProviderNetwork columns: provider_id, scheme_id, network_type, effective_from, effective_to
    network_types = ["PRIME_HOSPITAL", "GP_NETWORK", "PHARMACY_DIRECT", "SPECIALIST_NETWORK"]
    count = 0
    for provider_id in providers:
        nt = random.choice(network_types)
        db.add(ProviderNetwork(
            scheme_id=sid, provider_id=provider_id,
            network_type=nt,
            effective_from=date(2026, 1, 1), effective_to=None,
        ))
        count += 1
    await db.flush()
    print(f"  Provider Networks: seeded {count}")


# ---------------------------------------------------------------------------
# Chronic Registrations
# ---------------------------------------------------------------------------

async def seed_chronic_registrations(db: AsyncSession, sid: int):
    if (await db.execute(select(ChronicRegistration).where(ChronicRegistration.scheme_id == sid).limit(1))).scalar():
        print("  Chronic Registrations: already seeded")
        return

    members = [row[0] for row in (await db.execute(
        select(Member.id).where(Member.scheme_id == sid).limit(20)
    )).all()]

    # Get CDL-eligible ICD10 codes
    icd10s = (await db.execute(
        select(ICD10Code.id, ICD10Code.code, ICD10Code.is_cdl).where(ICD10Code.is_cdl == True).limit(10)
    )).all()

    if not members or not icd10s:
        print("  No members or CDL codes — skipping")
        return

    # Mining sector has higher prevalence of respiratory, cardiovascular, HIV
    registrations = [
        {"member_id": members[0], "icd10_code_id": icd10s[0][0], "application_date": date(2024, 3, 15),
         "status": "APPROVED", "decision_date": date(2024, 4, 1),
         "notes": "Type 2 diabetes. On metformin + glimepiride."},
        {"member_id": members[1], "icd10_code_id": icd10s[1][0] if len(icd10s) > 1 else icd10s[0][0],
         "application_date": date(2024, 6, 1),
         "status": "APPROVED", "decision_date": date(2024, 6, 15),
         "notes": "Hypertension stage 2. On amlodipine + enalapril."},
        {"member_id": members[2], "icd10_code_id": icd10s[2][0] if len(icd10s) > 2 else icd10s[0][0],
         "application_date": date(2025, 1, 10),
         "status": "APPROVED", "decision_date": date(2025, 2, 1),
         "notes": "HIV positive. ARV regimen TLD."},
        {"member_id": members[3], "icd10_code_id": icd10s[0][0],
         "application_date": date(2025, 4, 20),
         "status": "APPROVED", "decision_date": date(2025, 5, 1),
         "notes": "Type 2 diabetes + hypertension comorbidity."},
        {"member_id": members[5], "icd10_code_id": icd10s[3][0] if len(icd10s) > 3 else icd10s[0][0],
         "application_date": date(2025, 8, 1),
         "status": "PENDING",
         "notes": "Asthma. Occupational exposure history — NIOH report attached."},
        {"member_id": members[8], "icd10_code_id": icd10s[1][0] if len(icd10s) > 1 else icd10s[0][0],
         "application_date": date(2025, 11, 5),
         "status": "APPROVED", "decision_date": date(2025, 12, 1),
         "notes": "Hypertension. Family history, underground worker."},
        {"member_id": members[10] if len(members) > 10 else members[4],
         "icd10_code_id": icd10s[4][0] if len(icd10s) > 4 else icd10s[0][0],
         "application_date": date(2026, 2, 14),
         "status": "APPROVED", "decision_date": date(2026, 3, 1),
         "notes": "Epilepsy. Well-controlled on sodium valproate."},
    ]
    for r in registrations:
        db.add(ChronicRegistration(scheme_id=sid, **r))
    await db.flush()
    print(f"  Chronic Registrations: seeded {len(registrations)}")


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------

async def seed_disputes(db: AsyncSession, sid: int):
    if (await db.execute(select(Dispute).where(Dispute.scheme_id == sid).limit(1))).scalar():
        print("  Disputes: already seeded")
        return

    members = [row[0] for row in (await db.execute(
        select(Member.id).where(Member.scheme_id == sid).limit(10)
    )).all()]

    if not members:
        print("  No members — skipping")
        return

    # Dispute columns: dispute_number, member_id, claim_id, dispute_type, description,
    # status, date_received, member_deadline, admin_deadline, resolution, escalated_to_cms, cms_reference
    disputes = [
        {"dispute_number": "MDVH-DSP-2026-001", "member_id": members[0],
         "dispute_type": "CLAIM_REJECTION",
         "description": "Member disputes rejection of claim for pulmonary function testing. Argues condition is PMB-related occupational disease per ODMWA.",
         "status": "OPEN",
         "date_received": date(2026, 3, 10),
         "member_deadline": date(2026, 6, 8),
         "admin_deadline": date(2026, 4, 9)},
        {"dispute_number": "MDVH-DSP-2026-002", "member_id": members[2],
         "dispute_type": "BENEFIT_LIMIT",
         "description": "Member queries rapid exhaustion of GP benefit. Multiple dependant visits in Jan-Feb.",
         "status": "UPHELD",
         "date_received": date(2026, 2, 5),
         "member_deadline": date(2026, 5, 6),
         "admin_deadline": date(2026, 3, 7),
         "resolution": "Benefit correctly calculated. Member counselled on benefit management. No further action."},
        {"dispute_number": "MDVH-DSP-2026-003", "member_id": members[4],
         "dispute_type": "CONTRIBUTION",
         "description": "Member claims LJP should not apply as they had continuous cover with previous scheme (Bonitas). Certificate of membership submitted.",
         "status": "OPEN",
         "date_received": date(2026, 5, 15),
         "member_deadline": date(2026, 8, 13),
         "admin_deadline": date(2026, 6, 14)},
        {"dispute_number": "MDVH-DSP-2026-004",
         "member_id": members[6] if len(members) > 6 else members[1],
         "dispute_type": "AUTHORISATION",
         "description": "Pre-authorisation declined for TKR as clinical criteria not met. Member argues pain score and X-ray findings warrant surgery.",
         "status": "ESCALATED_TO_CMS",
         "date_received": date(2026, 1, 20),
         "member_deadline": date(2026, 4, 20),
         "admin_deadline": date(2026, 2, 19),
         "escalated_to_cms": True,
         "cms_reference": "CMS/2026/04521"},
    ]
    for d in disputes:
        db.add(Dispute(scheme_id=sid, **d))
    await db.flush()
    print(f"  Disputes: seeded {len(disputes)}")


# ---------------------------------------------------------------------------
# Underwriting Decisions
# ---------------------------------------------------------------------------

async def seed_underwriting_decisions(db: AsyncSession, sid: int):
    if (await db.execute(select(UnderwritingDecision).where(UnderwritingDecision.scheme_id == sid).limit(1))).scalar():
        print("  Underwriting Decisions: already seeded")
        return

    members = [(row[0], row[1]) for row in (await db.execute(
        select(Member.id, Member.join_date).where(Member.scheme_id == sid).limit(15)
    )).all()]

    if not members:
        print("  No members — skipping")
        return

    # Need a user_id for created_by
    from app.models.auth import User
    user_result = await db.execute(select(User.id).where(User.scheme_id == sid).limit(1))
    admin_id = user_result.scalar() or 1

    decisions = []
    for i, (mid, join_date) in enumerate(members):
        eff = join_date if join_date else date(2025, 1, 1)
        dec_date = eff - timedelta(days=14)
        if i < 10:
            decisions.append({
                "member_id": mid, "decision": "approved", "status": "active",
                "decision_date": dec_date, "effective_date": eff,
                "has_prior_cover": True, "prior_cover_years": 5,
                "general_wp_months": 0, "late_joiner_penalty_pct": 0,
                "created_by": admin_id,
                "notes": "Standard acceptance. Continuous prior cover verified.",
            })
        elif i < 12:
            wp_end = eff + timedelta(days=90)
            decisions.append({
                "member_id": mid, "decision": "approved", "status": "active",
                "decision_date": dec_date, "effective_date": eff,
                "has_prior_cover": False,
                "general_wp_months": 3, "general_wp_end_date": wp_end,
                "late_joiner_penalty_pct": 0,
                "created_by": admin_id,
                "notes": "First-time joiner. Standard 3-month general WP.",
            })
        else:
            decisions.append({
                "member_id": mid, "decision": "approved", "status": "active",
                "decision_date": dec_date, "effective_date": eff,
                "has_prior_cover": True, "prior_cover_break_days": 200,
                "is_late_joiner": True, "late_joiner_uncovered_years": 3,
                "general_wp_months": 0, "late_joiner_penalty_pct": 25,
                "created_by": admin_id,
                "notes": "Gap in cover > 90 days. 25% LJP applied per CMS Reg.7.",
            })

    for d in decisions:
        db.add(UnderwritingDecision(scheme_id=sid, **d))
    await db.flush()
    print(f"  Underwriting Decisions: seeded {len(decisions)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60)
    print("Comprehensive seed: MDV Health Medical Scheme")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scheme).where(Scheme.code == "MDVH"))
        scheme = result.scalar_one_or_none()
        if not scheme:
            print("ERROR: MDV Health (MDVH) scheme not found.")
            print("Run seed_mdv.py first to create the base scheme.")
            return

        sid = scheme.id
        print(f"Found scheme: {scheme.name} (id={sid})")
        print()

        print("Governance:")
        await seed_trustees(db, sid)
        await seed_principal_officer(db, sid)
        await seed_administrator(db, sid)
        await seed_mcos(db, sid)
        await seed_external_auditor(db, sid)
        await seed_statutory_actuary(db, sid)
        await seed_compliance_officer(db, sid)
        await seed_information_officer(db, sid)
        print()

        print("Employers:")
        await seed_employer_groups(db, sid)
        await seed_member_employer_history(db, sid)
        print()

        print("Intermediaries:")
        await seed_brokerages(db, sid)
        await seed_brokers(db, sid)
        await seed_commission_scales(db, sid)
        await seed_broker_appointments(db, sid)
        print()

        print("Plan config & rules:")
        await seed_copayment_rules(db, sid)
        await seed_provider_networks(db, sid)
        print()

        print("Clinical:")
        await seed_chronic_registrations(db, sid)
        print()

        print("Underwriting:")
        await seed_underwriting_decisions(db, sid)
        print()

        print("Disputes:")
        await seed_disputes(db, sid)
        print()

        await db.commit()
        print("=" * 60)
        print("Done. All MDVH seed data committed.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
