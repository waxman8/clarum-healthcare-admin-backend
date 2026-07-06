"""
Seed script for Demo Health Medical Scheme
Generates realistic South African healthcare data
"""
import asyncio
import random
import json
import os
import sys
from datetime import date, datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.auth import Scheme, User, AuditLog
from app.models.reference import ICD10Code, TariffCode, RejectionCode, PlanOption, DisciplineCode
from app.models.members import Member, Dependant, BenefitLimit, MemberStatusHistory
from app.models.providers import Provider
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.claims import Claim, ClaimLine
from app.models import billing as _billing_models  # noqa: F401 — registers billing mapper classes
from app.auth.security import get_password_hash
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {}
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def generate_sa_id_number(dob: date, gender: str) -> str:
    """Generate a valid SA ID number from date of birth and gender."""
    year = str(dob.year)[2:]
    month = f"{dob.month:02d}"
    day = f"{dob.day:02d}"
    gender_seq = random.randint(5000, 9999) if gender == "male" else random.randint(0, 4999)
    citizenship = "0"
    race_digit = "8"
    base = f"{year}{month}{day}{gender_seq:04d}{citizenship}{race_digit}"

    # Luhn algorithm checksum
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


SA_FIRST_NAMES_MALE = [
    "Themba", "Sipho", "Mandla", "Bongani", "Nkosi", "Lwazi", "Thabo", "Siyanda",
    "Pieter", "Johan", "Hendrik", "Francois", "Christiaan", "Ruan", "Werner",
    "James", "Michael", "David", "Andrew", "Robert",
    "Lungelo", "Sifiso", "Phiwayinkosi", "Mthokozisi", "Sandile",
    "Lehlohonolo", "Thabiso", "Mpho", "Kagiso", "Lesedi",
]

SA_FIRST_NAMES_FEMALE = [
    "Nomvula", "Zanele", "Thandi", "Nompumelelo", "Lindiwe", "Nokuthula", "Bongiwe",
    "Marie", "Anna", "Elmarie", "Liezel", "Anke", "Chantel", "Marlene",
    "Sarah", "Jennifer", "Amanda", "Lisa", "Michelle", "Karen",
    "Nosipho", "Ntombifuthi", "Hlengiwe", "Nokukhanya", "Simangele",
    "Lerato", "Dineo", "Boitumelo", "Kelebogile", "Mmapula",
]

SA_SURNAMES = [
    "Dlamini", "Nkosi", "Mthembu", "Zulu", "Ndlovu", "Khumalo", "Sithole",
    "Van der Merwe", "Botha", "Pretorius", "Du Plessis", "Nel", "Viljoen", "Steyn",
    "Smith", "Jones", "Williams", "Brown", "Taylor",
    "Mokoena", "Molefe", "Mahlangu", "Shabalala", "Mkhize",
    "Naidoo", "Pillay", "Govender", "Reddy", "Padayachee",
    "Cele", "Ntanzi", "Buthelezi", "Hadebe", "Majola",
]

CITIES = [
    "Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth",
    "Soweto", "Sandton", "Roodepoort", "Germiston", "Boksburg",
]


def random_cell():
    prefixes = ["071", "072", "073", "074", "076", "078", "079", "081", "082", "083", "084"]
    return f"{random.choice(prefixes)}{random.randint(1000000, 9999999)}"


def random_dob(min_age: int = 18, max_age: int = 70) -> date:
    today = date.today()
    age = random.randint(min_age, max_age)
    days_offset = random.randint(0, 364)
    return today - timedelta(days=age * 365 + days_offset)


async def seed_discipline_codes(db):
    """Seed BHF standard discipline codes. Idempotent."""
    BHF_CODES = [
        # Medical
        ("00", "General Practitioner", "MEDICAL"),
        ("01", "Specialist Physician (Internal Medicine)", "MEDICAL"),
        ("02", "General Surgeon", "MEDICAL"),
        ("03", "Orthopaedic Surgeon", "MEDICAL"),
        ("04", "Neurosurgeon", "MEDICAL"),
        ("05", "Cardiothoracic Surgeon", "MEDICAL"),
        ("06", "Plastic and Reconstructive Surgeon", "MEDICAL"),
        ("07", "Ophthalmologist", "MEDICAL"),
        ("08", "Otorhinolaryngologist (ENT)", "MEDICAL"),
        ("09", "Obstetrician and Gynaecologist", "MEDICAL"),
        ("10", "Paediatrician", "MEDICAL"),
        ("11", "Psychiatrist", "MEDICAL"),
        ("12", "Radiologist (Diagnostic)", "MEDICAL"),
        ("13", "Anaesthesiologist", "MEDICAL"),
        ("14", "Pathologist", "MEDICAL"),
        ("15", "Dermatologist", "MEDICAL"),
        ("16", "Urologist", "MEDICAL"),
        ("17", "Neurologist", "MEDICAL"),
        ("18", "Gastroenterologist", "MEDICAL"),
        ("19", "Oncologist / Haematologist", "MEDICAL"),
        ("20", "Rheumatologist", "MEDICAL"),
        ("21", "Endocrinologist", "MEDICAL"),
        ("22", "Pulmonologist", "MEDICAL"),
        ("23", "Cardiologist", "MEDICAL"),
        ("24", "Nephrologist", "MEDICAL"),
        ("25", "Infectious Disease Specialist", "MEDICAL"),
        ("26", "Allergist / Immunologist", "MEDICAL"),
        # Dental
        ("27", "General Dentist", "DENTAL"),
        ("28", "Dental Specialist", "DENTAL"),
        # Pharmacy
        ("29", "Pharmacist", "PHARMACY"),
        # Allied
        ("30", "Optometrist", "ALLIED"),
        ("31", "Physiotherapist", "ALLIED"),
        ("32", "Occupational Therapist", "ALLIED"),
        ("33", "Speech Therapist / Audiologist", "ALLIED"),
        ("34", "Psychologist", "ALLIED"),
        ("35", "Medical Social Worker", "ALLIED"),
        ("36", "Dietitian", "ALLIED"),
        ("37", "Biokineticist", "ALLIED"),
        ("38", "Private Nurse / Nursing Agency", "ALLIED"),
        ("39", "Emergency Medical Services", "ALLIED"),
        # Facilities
        ("40", "Private Hospital", "FACILITY"),
        ("41", "Public Hospital", "FACILITY"),
        ("42", "Day Clinic / Day Hospital", "FACILITY"),
        ("43", "Hospice", "FACILITY"),
        ("44", "Ambulance Service", "FACILITY"),
        ("45", "Pathology Laboratory", "FACILITY"),
        ("46", "Radiology Practice", "FACILITY"),
        ("47", "Pharmacy", "FACILITY"),
        ("48", "Optical Practice", "FACILITY"),
        ("49", "Dental Laboratory", "FACILITY"),
        ("50", "Medical Supplier / Appliance", "OTHER"),
    ]
    for code, description, category in BHF_CODES:
        exists = (await db.execute(
            select(DisciplineCode).where(DisciplineCode.code == code)
        )).scalar_one_or_none()
        if not exists:
            db.add(DisciplineCode(code=code, description=description, category=category))
    await db.flush()
    print(f"  Discipline codes: {len(BHF_CODES)} BHF codes seeded")


async def seed_database():
    async with AsyncSessionLocal() as db:
        print("Seeding BHF discipline codes...")
        await seed_discipline_codes(db)

        print("Creating scheme...")
        scheme = Scheme(
            name="Demo Health Medical Scheme",
            code="DHMS",
            registration_number="MS/DEV/2018",
            cms_accreditation_number="CMS/ACC/2018/001",
            is_active=True,
        )
        db.add(scheme)
        await db.flush()

        print("Creating plan options...")
        plan_hospital = PlanOption(
            scheme_id=scheme.id,
            name="Hospital Plan",
            code="HOSP",
            monthly_premium=185000,
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="NONE",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        plan_comprehensive = PlanOption(
            scheme_id=scheme.id,
            name="Comprehensive",
            code="COMP",
            monthly_premium=320000,
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="LIMIT",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        plan_executive = PlanOption(
            scheme_id=scheme.id,
            name="Executive",
            code="EXEC",
            monthly_premium=550000,
            is_active=True,
            hospital_network="OPEN",
            day_to_day_type="LIMIT",
            care_coordination_required=False,
            gp_referral_required=False,
            benefit_year=2026,
            tariff_multiplier=100,
        )
        db.add_all([plan_hospital, plan_comprehensive, plan_executive])
        await db.flush()

        print("Creating users...")
        users_data = [
            ("admin@demohealth.co.za", "Admin User", "super_admin"),
            ("schemeadmin@demohealth.co.za", "Scheme Administrator", "scheme_admin"),
            ("claims@demohealth.co.za", "Claims Processor", "claims_processor"),
            ("auth@demohealth.co.za", "Authorisation Officer", "authorisation_officer"),
            ("finance@demohealth.co.za", "Finance Officer", "finance_officer"),
            ("callcentre@demohealth.co.za", "Call Centre Agent", "call_centre_agent"),
        ]
        users = []
        for email, full_name, role in users_data:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash("Demo@1234"),
                role=role,
                is_active=True,
                scheme_id=scheme.id,
            )
            db.add(user)
            users.append(user)
        await db.flush()
        admin_user = users[0]
        claims_user = users[2]

        print("Creating ICD-10 codes...")
        icd10_codes = [
            ("J00", "Acute nasopharyngitis (common cold)", False),
            ("J06.9", "Acute upper respiratory infection, unspecified", False),
            ("J18.9", "Pneumonia, unspecified organism", True),
            ("J45.0", "Predominantly allergic asthma", True),
            ("J45.1", "Nonallergic asthma", True),
            ("I10", "Essential (primary) hypertension", True),
            ("I11.0", "Hypertensive heart disease with heart failure", True),
            ("I25.1", "Atherosclerotic heart disease of native coronary artery", True),
            ("I50.0", "Congestive heart failure", True),
            ("E11.9", "Type 2 diabetes mellitus without complications", True),
            ("E11.0", "Type 2 diabetes mellitus with hyperosmolarity", True),
            ("E78.0", "Pure hypercholesterolaemia", False),
            ("E66.0", "Obesity due to excess calories", False),
            ("K21.0", "Gastro-oesophageal reflux disease with oesophagitis", False),
            ("K29.7", "Gastritis, unspecified", False),
            ("K40.9", "Unilateral inguinal hernia without obstruction", False),
            ("K57.30", "Diverticulosis of large intestine without perforation", False),
            ("K80.10", "Calculus of gallbladder with chronic cholecystitis", True),
            ("K92.1", "Melaena", False),
            ("M54.5", "Low back pain", False),
            ("M79.3", "Panniculitis, unspecified", False),
            ("M05.9", "Rheumatoid arthritis, unspecified", True),
            ("M16.9", "Osteoarthritis of hip, unspecified", False),
            ("M17.9", "Osteoarthritis of knee, unspecified", False),
            ("N39.0", "Urinary tract infection, site not specified", False),
            ("N18.3", "Chronic kidney disease, stage 3", True),
            ("N40", "Hyperplasia of prostate", False),
            ("C18.9", "Malignant neoplasm of colon, unspecified", True),
            ("C50.9", "Malignant neoplasm of breast, unspecified", True),
            ("C34.1", "Malignant neoplasm of upper lobe, bronchus or lung", True),
            ("F32.1", "Moderate depressive episode", False),
            ("F41.1", "Generalized anxiety disorder", False),
            ("G43.9", "Migraine, unspecified", False),
            ("G40.9", "Epilepsy, unspecified", True),
            ("H26.9", "Cataract, unspecified", False),
            ("H35.3", "Degeneration of macula and posterior pole", False),
            ("R05", "Cough", False),
            ("R50.9", "Fever, unspecified", False),
            ("R51", "Headache", False),
            ("R55", "Syncope and collapse", False),
            ("S72.0", "Fracture of neck of femur", False),
            ("S82.1", "Fracture of proximal part of tibia", False),
            ("T14.0", "Superficial injury of unspecified body region", False),
            ("Z00.0", "General adult medical examination", False),
            ("Z12.5", "Encounter for screening for malignant neoplasm of prostate", False),
            ("Z30.0", "Encounter for general counselling and advice on contraception", False),
            ("Z34.0", "Encounter for supervision of normal first pregnancy", False),
            ("Z51.1", "Encounter for antineoplastic chemotherapy", True),
            ("O80", "Encounter for full-term uncomplicated delivery", True),
            ("A09", "Other and unspecified gastroenteritis and colitis of infectious origin", False),
        ]
        icd10_objects = []
        for code, desc, is_pmb in icd10_codes:
            existing = (await db.execute(select(ICD10Code).where(ICD10Code.code == code))).scalar_one_or_none()
            if existing:
                icd10_objects.append(existing)
            else:
                obj = ICD10Code(code=code, description=desc, is_pmb=is_pmb, is_active=True)
                db.add(obj)
                icd10_objects.append(obj)
        await db.flush()

        print("Creating tariff codes...")
        tariff_codes_data = [
            ("0190", "Initial consultation - General Practitioner", 45600, "GP"),
            ("0191", "Repeat consultation - General Practitioner", 32200, "GP"),
            ("0192", "After-hours consultation - General Practitioner", 68400, "GP"),
            ("0190x", "Telephonic consultation", 22800, "GP"),
            ("0201", "Initial consultation - Specialist", 87500, "SPEC"),
            ("0202", "Repeat consultation - Specialist", 65000, "SPEC"),
            ("0203", "Complex consultation - Specialist", 125000, "SPEC"),
            ("1000", "Hospitalisation per diem - general ward", 320000, "HOSP"),
            ("1001", "Hospitalisation per diem - ICU", 850000, "HOSP"),
            ("1002", "Hospitalisation per diem - high care", 520000, "HOSP"),
            ("2000", "Minor procedure - rooms", 185000, "PROC"),
            ("2001", "Intermediate surgical procedure", 450000, "PROC"),
            ("2002", "Major surgical procedure", 980000, "PROC"),
            ("2003", "Appendicectomy", 875000, "PROC"),
            ("2004", "Laparoscopic cholecystectomy", 1250000, "PROC"),
            ("2005", "Total hip replacement", 2500000, "PROC"),
            ("2006", "Total knee replacement", 2300000, "PROC"),
            ("2010", "Coronary artery bypass graft", 4500000, "PROC"),
            ("2011", "Angioplasty with stenting", 3200000, "PROC"),
            ("3000", "Full blood count (FBC)", 18500, "PATH"),
            ("3001", "Lipogram", 24200, "PATH"),
            ("3002", "HbA1c", 19800, "PATH"),
            ("3003", "Urine microscopy", 12500, "PATH"),
            ("3004", "HIV test", 15600, "PATH"),
            ("3005", "Glucose fasting", 11200, "PATH"),
            ("3006", "Liver function tests", 28500, "PATH"),
            ("3007", "Renal function", 22100, "PATH"),
            ("3008", "Thyroid function", 31800, "PATH"),
            ("4000", "Chest X-ray", 52000, "RAD"),
            ("4001", "Abdomen X-ray", 48000, "RAD"),
            ("4002", "CT scan brain", 380000, "RAD"),
            ("4003", "CT scan abdomen", 420000, "RAD"),
            ("4004", "MRI brain", 650000, "RAD"),
            ("4005", "MRI spine", 680000, "RAD"),
            ("4006", "Ultrasound abdomen", 185000, "RAD"),
            ("4007", "Ultrasound pelvis", 175000, "RAD"),
            ("4008", "Mammography", 165000, "RAD"),
            ("5000", "Oral examination - dentist", 32000, "DENT"),
            ("5001", "Dental X-ray (per film)", 18500, "DENT"),
            ("5002", "Restoration - amalgam, one surface", 68500, "DENT"),
            ("5003", "Extraction - forceps", 58000, "DENT"),
            ("5004", "Root canal treatment - anterior", 185000, "DENT"),
            ("5005", "Crown - porcelain fused to metal", 520000, "DENT"),
            ("6000", "Pharmacy dispensing fee", 5200, "PHARM"),
            ("6001", "Chronic medication dispensing", 8500, "PHARM"),
            ("7000", "Physiotherapy initial assessment", 65000, "PHYSIO"),
            ("7001", "Physiotherapy treatment session", 52000, "PHYSIO"),
            ("7002", "Occupational therapy assessment", 78000, "OT"),
            ("7003", "Speech therapy session", 68000, "ST"),
            ("8000", "Ophthalmic examination", 52000, "OPT"),
        ]
        tariff_objects = []
        for code, desc, rate, disc in tariff_codes_data:
            existing = (await db.execute(select(TariffCode).where(TariffCode.code == code))).scalar_one_or_none()
            if existing:
                tariff_objects.append(existing)
            else:
                obj = TariffCode(code=code, description=desc, nhrpl_rate=rate, discipline_code=disc, is_active=True)
                db.add(obj)
                tariff_objects.append(obj)
        await db.flush()

        print("Creating rejection codes...")
        rejection_codes_data = [
            ("BE01", "Benefit exhausted for benefit year", "Benefit"),
            ("BE02", "Benefit limit reached for this category", "Benefit"),
            ("NC01", "Service not covered under plan option", "Coverage"),
            ("NC02", "Elective procedure not covered", "Coverage"),
            ("NC03", "Cosmetic procedure not covered", "Coverage"),
            ("DUP1", "Duplicate claim - same date, provider and tariff", "Duplicate"),
            ("DUP2", "Possible duplicate - claim within 30 days", "Duplicate"),
            ("ME01", "Member not active on date of service", "Member"),
            ("ME02", "Dependant not registered", "Member"),
            ("PR01", "Provider not registered or not active", "Provider"),
            ("PR02", "Provider not contracted for this service type", "Provider"),
            ("CL01", "Missing or invalid ICD-10 code", "Clinical"),
            ("CL02", "Diagnosis does not support procedure", "Clinical"),
            ("AP01", "Prior authorisation required but not obtained", "Authorisation"),
            ("AP02", "Authorisation expired", "Authorisation"),
        ]
        for code, desc, cat in rejection_codes_data:
            existing = (await db.execute(select(RejectionCode).where(RejectionCode.code == code))).scalar_one_or_none()
            if not existing:
                db.add(RejectionCode(code=code, description=desc, category=cat))
        await db.flush()

        print("Creating benefit limits...")
        benefit_year = date.today().year
        benefit_configs = {
            "HOSP": [
                ("hospital", "rand", 15000000),
                ("dentistry", "rand", 320000),
                ("optometry", "rand", 0),
                ("chronic", "rand", 0),
                ("gp_visits", "visits", 6),
            ],
            "COMP": [
                ("hospital", "rand", 25000000),
                ("dentistry", "rand", 750000),
                ("optometry", "rand", 250000),
                ("chronic", "rand", 5000000),
                ("gp_visits", "visits", 24),
            ],
            "EXEC": [
                ("hospital", "rand", 50000000),
                ("dentistry", "rand", 1500000),
                ("optometry", "rand", 500000),
                ("chronic", "rand", 12000000),
                ("gp_visits", "visits", 999),
            ],
        }
        plan_map = {"HOSP": plan_hospital, "COMP": plan_comprehensive, "EXEC": plan_executive}
        for plan_code, limits in benefit_configs.items():
            plan = plan_map[plan_code]
            for cat, ltype, limit_val in limits:
                applied = int(limit_val * random.uniform(0.1, 0.6)) if limit_val > 0 else 0
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

        print("Creating providers...")
        providers_data = [
            ("PR001001", "GP", "gp", "Sandton City Medical Centre", "4680123456789", True, True, "info@sandtonmedical.co.za", "0114445555"),
            ("PR002002", "HOSP", "hospital", "Netcare Milpark Hospital", "4560987654321", True, True, "admissions@milpark.co.za", "0114805000"),
            ("PR003003", "SPEC", "specialist", "Dr Sarah van der Merwe", "4120111222333", False, True, "sarah@vdmspecialist.co.za", "0217895623"),
            ("PR004004", "PHARM", "pharmacy", "Clicks Pharmacy Rosebank", "4890444555666", False, True, "rosebank@clicks.co.za", "0117887890"),
            ("PR005005", "DENT", "dentist", "Soweto Dental Clinic", "4230777888999", False, True, "info@sowetodental.co.za", "0118381234"),
        ]
        provider_objects = []
        for pnum, disc, ptype, name, vat, is_dsp, is_active, email, phone in providers_data:
            existing = (await db.execute(select(Provider).where(Provider.practice_number == pnum))).scalar_one_or_none()
            if existing:
                provider_objects.append(existing)
            else:
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

        print("Creating members...")
        statuses = (
            ["active"] * 35 +
            ["pending"] * 5 +
            ["suspended"] * 5 +
            ["lapsed"] * 3 +
            ["cancelled"] * 2
        )
        random.shuffle(statuses)

        plan_options = [plan_hospital, plan_comprehensive, plan_executive]
        plan_weights = [0.4, 0.4, 0.2]

        member_objects = []
        for i, status in enumerate(statuses):
            gender = random.choice(["male", "female"])
            if gender == "male":
                first_name = random.choice(SA_FIRST_NAMES_MALE)
            else:
                first_name = random.choice(SA_FIRST_NAMES_FEMALE)
            surname = random.choice(SA_SURNAMES)

            dob = random_dob(18, 65)
            id_number = generate_sa_id_number(dob, gender)

            plan = random.choices(plan_options, weights=plan_weights)[0]

            join_date = date.today() - timedelta(days=random.randint(30, 2000))
            termination_date = None
            if status in ["lapsed", "cancelled"]:
                termination_date = date.today() - timedelta(days=random.randint(10, 180))

            email = f"{first_name.lower().replace(' ', '')}.{surname.lower().replace(' ', '').replace("'", '')}@{random.choice(['gmail.com', 'outlook.com', 'webmail.co.za'])}"
            cell = random_cell()

            seq = i + 1
            year = date.today().year
            membership_number = f"DHMS-{year}-{seq:06d}"

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

        # Status history for all members
        for member in member_objects:
            history = MemberStatusHistory(
                member_id=member.id,
                old_status=None,
                new_status="active",
                changed_by=admin_user.id,
                reason="Initial enrolment",
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

        print("Creating dependants...")
        relationships_male = ["spouse", "child"]
        relationships_female = ["spouse", "child"]
        active_members = [m for m in member_objects if m.status == "active"]

        for member in active_members:
            num_deps = random.choices([0, 1, 2, 3], weights=[0.3, 0.3, 0.25, 0.15])[0]
            for dep_idx in range(num_deps):
                dep_code = f"0{dep_idx + 1}"
                if dep_idx == 0 and random.random() > 0.3:
                    relationship = "spouse"
                    dep_gender = "female" if member.gender == "male" else "male"
                    dep_dob = random_dob(20, 60)
                    dep_first = random.choice(SA_FIRST_NAMES_FEMALE if dep_gender == "female" else SA_FIRST_NAMES_MALE)
                else:
                    relationship = "child"
                    dep_gender = random.choice(["male", "female"])
                    dep_dob = random_dob(0, 17)
                    dep_first = random.choice(SA_FIRST_NAMES_MALE if dep_gender == "male" else SA_FIRST_NAMES_FEMALE)

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

        print("Creating authorisations...")
        auth_statuses = (
            ["pending"] * 4 +
            ["approved"] * 4 +
            ["declined"] * 2
        )
        auth_types = ["hospital_admission", "specialist_referral", "procedure", "chronic_medication"]
        icd10_pmb_codes = [c for c in icd10_codes if c[2]]  # PMB ones
        icd10_all_codes = icd10_codes

        auth_objects = []
        for i, auth_status in enumerate(auth_statuses):
            member = random.choice(active_members)
            provider = random.choice(provider_objects)
            auth_type = random.choice(auth_types)

            icd_codes = [random.choice(icd10_all_codes)[0] for _ in range(random.randint(1, 3))]
            proc_codes = [random.choice(tariff_codes_data)[0] for _ in range(random.randint(1, 2))]

            created_at = datetime.now() - timedelta(days=random.randint(1, 60))
            auth_number = f"DHMS-{date.today().year}-{i + 1:08d}"

            approved_days = None
            if auth_status == "approved":
                approved_days = random.randint(1, 7)

            auth = Authorisation(
                auth_number=auth_number,
                member_id=member.id,
                requesting_provider_id=provider.id,
                icd10_codes=json.dumps(icd_codes),
                procedure_codes=json.dumps(proc_codes),
                auth_type=auth_type,
                status=auth_status,
                approved_days=approved_days,
                clinical_notes="Clinical notes reviewed and assessed." if auth_status != "pending" else None,
                created_by=admin_user.id,
                created_at=created_at,
            )
            db.add(auth)
            auth_objects.append(auth)
        await db.flush()

        for auth in auth_objects:
            num_lines = random.randint(1, 3)
            for j in range(num_lines):
                tariff = random.choice(tariff_codes_data)
                qty_req = random.randint(1, 5)
                qty_appr = None
                reason = None
                if auth.status == "approved":
                    qty_appr = qty_req
                elif auth.status == "declined":
                    qty_appr = 0
                    reason = "Service not covered under current plan option"
                elif auth.status == "partial":
                    qty_appr = max(1, qty_req - 1)

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

        print("Creating claims...")
        claim_statuses = (
            ["approved"] * 6 +
            ["partial"] * 4 +
            ["rejected"] * 3 +
            ["paid"] * 4 +
            ["received"] * 2 +
            ["in_adjudication"] * 1
        )
        random.shuffle(claim_statuses)

        claim_types = ["medical", "hospital", "pharmacy", "dental", "specialist"]

        for i, claim_status in enumerate(claim_statuses):
            member = random.choice(active_members)
            provider = random.choice(provider_objects)
            claim_type = random.choice(claim_types)

            dos_from = date.today() - timedelta(days=random.randint(1, 90))
            dos_to = dos_from + timedelta(days=random.randint(0, 5))
            date_received = dos_to + timedelta(days=random.randint(1, 14))
            if date_received > date.today():
                date_received = date.today()

            claim_number = f"CLM-{date.today().strftime('%Y%m')}-{i + 1:06d}"

            # Generate billed amount 3000-150000 cents
            total_billed = random.randint(3000, 150000)
            total_approved = 0
            total_member_liability = 0
            total_scheme_liability = 0

            if claim_status in ["approved", "paid"]:
                total_approved = total_billed
                total_scheme_liability = total_approved
            elif claim_status == "partial":
                total_approved = int(total_billed * random.uniform(0.5, 0.8))
                total_member_liability = total_billed - total_approved
                total_scheme_liability = total_approved
            elif claim_status == "rejected":
                total_approved = 0
                total_member_liability = total_billed

            is_pmb = random.random() < 0.2

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
                adjudicated_at=datetime.now() - timedelta(days=random.randint(0, 30)) if claim_status not in ["received", "in_adjudication"] else None,
            )
            db.add(claim)
            await db.flush()

            # Add claim lines
            num_lines = random.randint(1, 4)
            line_total = total_billed
            for j in range(num_lines):
                tariff = random.choice(tariff_codes_data)
                icd10 = random.choice(icd10_codes)

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
                    if j == 0:
                        approved_line = billed
                    else:
                        approved_line = int(billed * random.uniform(0.0, 0.9))
                        if approved_line < billed:
                            rejection_code = "BE01"
                            rejection_text = "Benefit limit reached"
                elif claim_status == "rejected":
                    approved_line = 0
                    rejection_code = "NC01"
                    rejection_text = "Service not covered under plan option"

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
        print("Seed data created successfully!")
        print("\nLogin credentials:")
        print("  admin@demohealth.co.za / Demo@1234 (super_admin)")
        print("  schemeadmin@demohealth.co.za / Demo@1234 (scheme_admin)")
        print("  claims@demohealth.co.za / Demo@1234 (claims_processor)")
        print("  auth@demohealth.co.za / Demo@1234 (authorisation_officer)")
        print("  finance@demohealth.co.za / Demo@1234 (finance_officer)")
        print("  callcentre@demohealth.co.za / Demo@1234 (call_centre_agent)")


if __name__ == "__main__":
    asyncio.run(seed_database())
