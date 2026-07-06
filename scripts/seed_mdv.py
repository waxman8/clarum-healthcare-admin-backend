"""
Seed script for MDV Health Medical Scheme (second scheme — demonstrates data separation)
"""
import asyncio
import random
import json
import os
import sys
from datetime import date, datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import Base, engine, AsyncSessionLocal
from app.models.auth import Scheme, User, AuditLog
from app.models.reference import ICD10Code, TariffCode, RejectionCode, PlanOption
from app.models.members import Member, Dependant, BenefitLimit, MemberStatusHistory
from app.models.providers import Provider
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.claims import Claim, ClaimLine
from app.models import billing as _billing_models  # noqa: F401 — registers billing mapper classes
from app.auth.security import get_password_hash


def generate_sa_id_number(dob: date, gender: str) -> str:
    year = str(dob.year)[2:]
    month = f"{dob.month:02d}"
    day = f"{dob.day:02d}"
    gender_seq = random.randint(5000, 9999) if gender == "male" else random.randint(0, 4999)
    citizenship = "0"
    race_digit = "8"
    base = f"{year}{month}{day}{gender_seq:04d}{citizenship}{race_digit}"
    total = 0
    for i, digit in enumerate(base):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    checksum = (10 - (total % 10)) % 10
    return f"{base}{checksum}"


# MDV Health uses a different demographic mix — more corporate/mining sector
MDV_FIRST_NAMES_MALE = [
    "Siphamandla", "Bonginkosi", "Nhlanhla", "Siyabonga", "Mbuso",
    "Leon", "Gerhard", "Danie", "Kobus", "Arno",
    "Trevor", "Kevin", "Shane", "Byron", "Deon",
    "Vusi", "Sibusiso", "Ntokozo", "Mduduzi", "Siyethemba",
    "Refilwe", "Tshepo", "Tumelo", "Oratile", "Kgomotso",
]

MDV_FIRST_NAMES_FEMALE = [
    "Nokukhanya", "Sbongile", "Ntombizonke", "Phindile", "Sindisiwe",
    "Elsa", "Rina", "Ansie", "Dalene", "Petro",
    "Cindy", "Vanessa", "Natalie", "Robyn", "Chantal",
    "Ntombi", "Nokwanda", "Lungile", "Thobile", "Nompilo",
    "Palesa", "Nthabiseng", "Morongwe", "Kelebogile", "Gaone",
]

MDV_SURNAMES = [
    "Shabalala", "Zwane", "Nzama", "Buthelezi", "Ntanzi",
    "Kruger", "Marais", "Swanepoel", "Lombard", "Myburgh",
    "Adendorff", "Coetzee", "Joubert", "Erasmus", "Hugo",
    "Sibiya", "Ngwenya", "Mkhize", "Cele", "Hadebe",
    "Maluleka", "Sefatsa", "Sekhwela", "Tshivhula", "Mphela",
    "Fernandez", "Govender", "Naidoo", "Chetty", "Moodley",
]

MDV_CITIES = [
    "Rustenburg", "Witbank", "Middelburg", "Polokwane", "Mokopane",
    "Steelpoort", "Burgersfort", "Phalaborwa", "Lydenburg", "Secunda",
]


def random_cell():
    prefixes = ["071", "072", "073", "074", "076", "078", "079", "081", "082", "083", "084"]
    return f"{random.choice(prefixes)}{random.randint(1000000, 9999999)}"


def random_dob(min_age: int = 18, max_age: int = 60) -> date:
    today = date.today()
    age = random.randint(min_age, max_age)
    days_offset = random.randint(0, 364)
    return today - timedelta(days=age * 365 + days_offset)


async def seed_mdv():
    async with AsyncSessionLocal() as db:
        # Check if MDV already exists
        result = await db.execute(select(Scheme).where(Scheme.code == "MDVH"))
        existing = result.scalar_one_or_none()
        if existing:
            print("MDV Health scheme already exists. Aborting.")
            return

        print("Creating MDV Health scheme...")
        scheme = Scheme(
            name="MDV Health Medical Scheme",
            code="MDVH",
            registration_number="MS/MDV/2014",
            cms_accreditation_number="CMS/ACC/2014/007",
            is_active=True,
        )
        db.add(scheme)
        await db.flush()

        print("Creating MDV plan options (mining/industrial sector focus)...")
        plan_core = PlanOption(
            scheme_id=scheme.id,
            name="Core Benefit",
            code="CORE",
            monthly_premium=142000,  # R1 420/mo
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="LIMIT",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        plan_plus = PlanOption(
            scheme_id=scheme.id,
            name="Plus Option",
            code="PLUS",
            monthly_premium=278000,  # R2 780/mo
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="LIMIT",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        plan_premier = PlanOption(
            scheme_id=scheme.id,
            name="Premier",
            code="PREM",
            monthly_premium=480000,  # R4 800/mo
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="LIMIT",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        db.add_all([plan_core, plan_plus, plan_premier])
        await db.flush()

        print("Creating MDV users...")
        users_data = [
            ("superadmin@mdvhealth.co.za", "MDV Super Admin", "super_admin"),
            ("schemeadmin@mdvhealth.co.za", "MDV Scheme Administrator", "scheme_admin"),
            ("claimsprocessor@mdvhealth.co.za", "MDV Claims Processor", "claims_processor"),
            ("authorisationofficer@mdvhealth.co.za", "MDV Authorisation Officer", "authorisation_officer"),
            ("finance@mdvhealth.co.za", "MDV Finance Officer", "finance_officer"),
            ("callcentre@mdvhealth.co.za", "MDV Call Centre Agent", "call_centre_agent"),
        ]
        users = []
        for email, full_name, role in users_data:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash("MDVH@1234"),
                role=role,
                is_active=True,
                scheme_id=scheme.id,
            )
            db.add(user)
            users.append(user)
        await db.flush()
        admin_user = users[0]
        claims_user = users[2]

        # Fetch shared reference data (ICD-10, tariff codes) — these are global
        icd10_result = await db.execute(select(ICD10Code).where(ICD10Code.is_active == True))
        icd10_objects = icd10_result.scalars().all()

        tariff_result = await db.execute(select(TariffCode).where(TariffCode.is_active == True))
        tariff_objects = tariff_result.scalars().all()

        print("Creating benefit limits for MDV plans...")
        benefit_year = date.today().year
        benefit_configs = {
            "CORE": [
                ("hospital", "rand", 10000000),    # R100k
                ("dentistry", "rand", 180000),      # R1 800
                ("optometry", "rand", 0),
                ("chronic", "rand", 0),
                ("gp_visits", "visits", 4),
            ],
            "PLUS": [
                ("hospital", "rand", 20000000),    # R200k
                ("dentistry", "rand", 600000),     # R6 000
                ("optometry", "rand", 180000),     # R1 800
                ("chronic", "rand", 3500000),      # R35k
                ("gp_visits", "visits", 18),
            ],
            "PREM": [
                ("hospital", "rand", 40000000),   # R400k
                ("dentistry", "rand", 1200000),   # R12k
                ("optometry", "rand", 400000),    # R4k
                ("chronic", "rand", 10000000),    # R100k
                ("gp_visits", "visits", 999),
            ],
        }
        plan_map = {"CORE": plan_core, "PLUS": plan_plus, "PREM": plan_premier}
        for plan_code, limits in benefit_configs.items():
            plan = plan_map[plan_code]
            for cat, ltype, limit_val in limits:
                applied = int(limit_val * random.uniform(0.05, 0.55)) if limit_val > 0 else 0
                bl = BenefitLimit(
                    plan_option_id=plan.id,
                    benefit_category=cat,
                    limit_type=ltype,
                    limit_value=limit_val,
                    applied_value=applied,
                    benefit_year=benefit_year,
                )
                db.add(bl)
        await db.flush()

        print("Creating MDV-specific providers...")
        mdv_providers_data = [
            ("PR010011", "GP", "gp", "Rustenburg Medical Centre", "4680123400011", True, True, "admin@rustenburgmed.co.za", "0147920100"),
            ("PR010022", "HOSP", "hospital", "Life Mercado Hospital", "4560987600022", True, True, "admit@lifemercado.co.za", "0147240400"),
            ("PR010033", "SPEC", "specialist", "Dr Gerhard Swanepoel Inc.", "4120111200033", False, True, "gswanepoel@specmed.co.za", "0147891100"),
            ("PR010044", "PHARM", "pharmacy", "Dis-Chem Rustenburg", "4890444500044", False, True, "rustenburg@dischem.co.za", "0147920900"),
            ("PR010055", "DENT", "dentist", "Platinum Dental Studio", "4230777800055", False, True, "info@platdental.co.za", "0147200550"),
            ("PR010066", "SPEC", "specialist", "Dr Nokuthula Dlamini", "4120333400066", False, True, "ndlamini@specialist.co.za", "0148001234"),
        ]
        provider_objects = []
        for pnum, disc, ptype, name, vat, is_dsp, is_active, email, phone in mdv_providers_data:
            p = Provider(
                practice_number=pnum,
                discipline_code=disc,
                provider_type=ptype,
                trading_name=name,
                vat_number=vat,
                is_dsp=is_dsp,
                is_active=is_active,
                contact_email=email,
                contact_phone=phone,
            )
            db.add(p)
            provider_objects.append(p)
        await db.flush()

        print("Creating MDV members (30 members)...")
        # MDV has 30 members — predominantly active, mining sector demographic
        statuses = (
            ["active"] * 22 +
            ["pending"] * 3 +
            ["suspended"] * 3 +
            ["lapsed"] * 1 +
            ["cancelled"] * 1
        )
        random.shuffle(statuses)

        plan_options = [plan_core, plan_plus, plan_premier]
        plan_weights = [0.45, 0.40, 0.15]  # More core plan usage vs Demo Health
        
        member_objects = []
        for i, status in enumerate(statuses):
            gender = random.choice(["male", "female"])
            if gender == "male":
                first_name = random.choice(MDV_FIRST_NAMES_MALE)
            else:
                first_name = random.choice(MDV_FIRST_NAMES_FEMALE)
            surname = random.choice(MDV_SURNAMES)

            dob = random_dob(22, 58)  # Working-age focus
            id_number = generate_sa_id_number(dob, gender)
            plan = random.choices(plan_options, weights=plan_weights)[0]

            join_date = date.today() - timedelta(days=random.randint(60, 3600))
            termination_date = None
            if status in ["lapsed", "cancelled"]:
                termination_date = date.today() - timedelta(days=random.randint(15, 120))

            clean_surname = surname.lower().replace(' ', '').replace("'", '')
            email = f"{first_name.lower().replace(' ', '')}.{clean_surname}@{random.choice(['gmail.com', 'yahoo.com', 'webmail.co.za', 'mweb.co.za'])}"
            cell = random_cell()

            seq = i + 1
            year = date.today().year
            membership_number = f"MDVH-{year}-{seq:06d}"

            member = Member(
                scheme_id=scheme.id,
                membership_number=membership_number,
                id_number=id_number,
                first_name=first_name,
                surname=surname,
                date_of_birth=dob,
                gender=gender,
                email=email,
                cell_number=cell,
                plan_option_id=plan.id,
                status=status,
                join_date=join_date,
                termination_date=termination_date,
            )
            db.add(member)
            member_objects.append(member)

        await db.flush()

        for member in member_objects:
            history = MemberStatusHistory(
                member_id=member.id,
                old_status=None,
                new_status="active",
                changed_by=admin_user.id,
                reason="Initial enrolment via employer group",
                changed_at=datetime.combine(member.join_date, datetime.min.time()),
            )
            db.add(history)
            if member.status != "active":
                history2 = MemberStatusHistory(
                    member_id=member.id,
                    old_status="active",
                    new_status=member.status,
                    changed_by=admin_user.id,
                    reason=f"Status changed to {member.status}",
                )
                db.add(history2)
        await db.flush()

        print("Creating MDV dependants...")
        active_members = [m for m in member_objects if m.status == "active"]

        for member in active_members:
            # Mining sector — slightly larger families on average
            num_deps = random.choices([0, 1, 2, 3, 4], weights=[0.2, 0.25, 0.3, 0.15, 0.1])[0]
            for dep_idx in range(num_deps):
                dep_code = f"0{dep_idx + 1}"
                if dep_idx == 0 and random.random() > 0.25:
                    relationship = "spouse"
                    dep_gender = "female" if member.gender == "male" else "male"
                    dep_dob = random_dob(20, 55)
                    dep_first = random.choice(MDV_FIRST_NAMES_FEMALE if dep_gender == "female" else MDV_FIRST_NAMES_MALE)
                else:
                    relationship = "child"
                    dep_gender = random.choice(["male", "female"])
                    dep_dob = random_dob(1, 20)
                    dep_first = random.choice(MDV_FIRST_NAMES_MALE if dep_gender == "male" else MDV_FIRST_NAMES_FEMALE)

                dep_id = generate_sa_id_number(dep_dob, dep_gender)
                dep = Dependant(
                    member_id=member.id,
                    dependant_relationship=relationship,
                    id_number=dep_id,
                    first_name=dep_first,
                    surname=member.surname,
                    date_of_birth=dep_dob,
                    gender=dep_gender,
                    status="active",
                    dependant_code=dep_code,
                )
                db.add(dep)
        await db.flush()

        print("Creating MDV authorisations...")
        icd10_data = [(c.code, c.description, c.is_pmb) for c in icd10_objects]
        tariff_data = [(t.code, t.description, t.nhrpl_rate) for t in tariff_objects]

        auth_statuses = (
            ["pending"] * 3 +
            ["approved"] * 4 +
            ["declined"] * 1 +
            ["expired"] * 1
        )
        auth_types = ["hospital_admission", "specialist_referral", "procedure", "chronic_medication", "elective"]

        auth_objects = []
        for i, auth_status in enumerate(auth_statuses):
            member = random.choice(active_members)
            provider = random.choice(provider_objects)
            auth_type = random.choice(auth_types)

            icd_codes = [random.choice(icd10_data)[0] for _ in range(random.randint(1, 2))]
            proc_codes = [random.choice(tariff_data)[0] for _ in range(random.randint(1, 2))]

            created_at = datetime.now() - timedelta(days=random.randint(1, 90))
            auth_number = f"MDVH-{date.today().year}-{i + 1:08d}"

            approved_days = None
            if auth_status == "approved":
                approved_days = random.randint(2, 10)

            auth = Authorisation(
                auth_number=auth_number,
                member_id=member.id,
                requesting_provider_id=provider.id,
                icd10_codes=json.dumps(icd_codes),
                procedure_codes=json.dumps(proc_codes),
                auth_type=auth_type,
                status=auth_status,
                approved_days=approved_days,
                clinical_notes="Clinical review completed." if auth_status not in ["pending"] else None,
                created_by=admin_user.id,
                created_at=created_at,
            )
            db.add(auth)
            auth_objects.append(auth)
        await db.flush()

        for auth in auth_objects:
            num_lines = random.randint(1, 3)
            for j in range(num_lines):
                tariff = random.choice(tariff_data)
                qty_req = random.randint(1, 5)
                qty_appr = None
                reason = None
                if auth.status == "approved":
                    qty_appr = qty_req
                elif auth.status == "declined":
                    qty_appr = 0
                    reason = "Elective procedure deferred pending specialist motivation"
                elif auth.status == "expired":
                    qty_appr = qty_req
                    reason = None

                line = AuthorisationLine(
                    auth_id=auth.id,
                    tariff_code=tariff[0],
                    description=tariff[1],
                    quantity_requested=qty_req,
                    quantity_approved=qty_appr,
                    reason_declined=reason,
                )
                db.add(line)
        await db.flush()

        print("Creating MDV claims (15 claims)...")
        claim_statuses = (
            ["approved"] * 4 +
            ["partial"] * 3 +
            ["rejected"] * 2 +
            ["paid"] * 3 +
            ["received"] * 2 +
            ["in_adjudication"] * 1
        )
        random.shuffle(claim_statuses)

        claim_types = ["medical", "hospital", "pharmacy", "specialist", "occupational_health"]

        for i, claim_status in enumerate(claim_statuses):
            member = random.choice(active_members)
            provider = random.choice(provider_objects)
            claim_type = random.choice(claim_types)

            dos_from = date.today() - timedelta(days=random.randint(1, 120))
            dos_to = dos_from + timedelta(days=random.randint(0, 7))
            date_received = dos_to + timedelta(days=random.randint(1, 21))
            if date_received > date.today():
                date_received = date.today()

            claim_number = f"CLM-MDVH-{date.today().strftime('%Y%m')}-{i + 1:06d}"

            total_billed = random.randint(5000, 200000)
            total_approved = 0
            total_member_liability = 0
            total_scheme_liability = 0

            if claim_status in ["approved", "paid"]:
                total_approved = total_billed
                total_scheme_liability = total_approved
            elif claim_status == "partial":
                total_approved = int(total_billed * random.uniform(0.45, 0.85))
                total_member_liability = total_billed - total_approved
                total_scheme_liability = total_approved
            elif claim_status == "rejected":
                total_approved = 0
                total_member_liability = total_billed

            is_pmb = random.random() < 0.15

            claim = Claim(
                claim_number=claim_number,
                scheme_id=scheme.id,
                member_id=member.id,
                provider_id=provider.id,
                date_of_service_from=dos_from,
                date_of_service_to=dos_to,
                date_received=date_received,
                claim_type=claim_type,
                status=claim_status,
                total_billed=total_billed,
                total_approved=total_approved,
                total_member_liability=total_member_liability,
                total_scheme_liability=total_scheme_liability,
                is_pmb=is_pmb,
                adjudicated_by=claims_user.id if claim_status not in ["received", "in_adjudication"] else None,
                adjudicated_at=datetime.now() - timedelta(days=random.randint(0, 45)) if claim_status not in ["received", "in_adjudication"] else None,
            )
            db.add(claim)
            await db.flush()

            num_lines = random.randint(1, 3)
            line_total = total_billed
            for j in range(num_lines):
                tariff = random.choice(tariff_data)
                icd10 = random.choice(icd10_data)

                if j == num_lines - 1:
                    billed = line_total
                else:
                    billed = int(line_total / (num_lines - j) * random.uniform(0.8, 1.2))
                    billed = max(1000, min(billed, line_total - (num_lines - j - 1) * 1000))
                    line_total -= billed

                approved_line = 0
                rejection_code = None
                rejection_text = None
                is_pmb_line = icd10[2]

                if claim_status in ["approved", "paid"]:
                    approved_line = billed
                elif claim_status == "partial":
                    approved_line = billed if j == 0 else int(billed * random.uniform(0.0, 0.9))
                    if approved_line < billed:
                        rejection_code = "BE02"
                        rejection_text = "Benefit limit reached for this category"
                elif claim_status == "rejected":
                    approved_line = 0
                    rejection_code = "NC01"
                    rejection_text = "Service not covered under MDV Core Benefit plan"

                line = ClaimLine(
                    claim_id=claim.id,
                    tariff_code=tariff[0],
                    description=tariff[1],
                    icd10_code=icd10[0],
                    quantity=1,
                    billed_amount=billed,
                    approved_amount=approved_line,
                    nhrpl_rate=tariff[2],
                    member_liability=max(0, billed - approved_line),
                    rejection_reason_code=rejection_code,
                    rejection_reason_text=rejection_text,
                    is_pmb_line=is_pmb_line,
                )
                db.add(line)

        await db.commit()

        print("\n" + "=" * 60)
        print("MDV Health Medical Scheme seeded successfully!")
        print("=" * 60)
        print("\nScheme: MDV Health Medical Scheme (MDVH)")
        print("Plans:  Core Benefit (R1 420/mo) | Plus (R2 780/mo) | Premier (R4 800/mo)")
        print(f"Members: 30 ({len(active_members)} active)")
        print("Claims:  15  |  Authorisations: 9  |  Providers: 6")
        print("\nLogin credentials (password: MDVH@1234):")
        print("  superadmin@mdvhealth.co.za       — super_admin")
        print("  schemeadmin@mdvhealth.co.za — scheme_admin")
        print("  claimsprocessor@mdvhealth.co.za      — claims_processor")
        print("  authorisationofficer@mdvhealth.co.za        — authorisation_officer")
        print("  finance@mdvhealth.co.za     — finance_officer")
        print("  callcentre@mdvhealth.co.za  — call_centre_agent")
        print("\nData separation: MDV users see ONLY MDV members, claims and authorisations.")
        print("Demo Health users see ONLY Demo Health data.")


if __name__ == "__main__":
    asyncio.run(seed_mdv())
