"""
Unified Seed Script for Demo Schemes: DHMS and MDVH.
Restores demo data for demohealth.co.za and mdvhealth.co.za while ensuring 
compatibility with the latest system schema (billing, balances, themes).
"""
import asyncio
import random
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.database import Base, engine, AsyncSessionLocal
from app.models.auth import Scheme, User, AuditLog, SchemeTheme, UserSchemeMembership
from app.models.reference import ICD10Code, TariffCode, RejectionCode, PlanOption
from app.models.members import Member, Dependant, BenefitLimit, MemberStatusHistory
from app.models.providers import Provider
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.claims import Claim, ClaimLine
from app.models.billing import ContributionRate, BenefitBalance
from app.auth.security import get_password_hash
from app.services.benefit_balance_service import initialise_benefit_balances

# Use engine and sessions from app.database

# --- Helper Utilities ---

def generate_sa_id_number(dob: date, gender: str) -> str:
    year = str(dob.year)[2:]
    month = f"{dob.month:02d}"
    day = f"{dob.day:02d}"
    gender_seq = random.randint(5000, 9999) if gender.lower() == "male" else random.randint(0, 4999)
    base = f"{year}{month}{day}{gender_seq:04d}08"
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

def random_dob(min_age: int = 18, max_age: int = 70) -> date:
    age = random.randint(min_age, max_age)
    return date.today() - timedelta(days=age * 365 + random.randint(0, 364))

def random_cell():
    return f"0{random.choice(['71', '72', '73', '74', '76', '82', '83'])}{random.randint(1000000, 9999999)}"

# --- Data Constants ---

SA_FIRST_NAMES_MALE = ["Themba", "Sipho", "Mandla", "Bongani", "Nkosi", "Lwazi", "Thabo", "Siyanda", "Pieter", "Johan"]
SA_FIRST_NAMES_FEMALE = ["Nomvula", "Zanele", "Thandi", "Nompumelelo", "Lindiwe", "Marie", "Anna", "Liezel"]
SA_SURNAMES = ["Dlamini", "Nkosi", "Mthembu", "Zulu", "Ndlovu", "Khumalo", "Van der Merwe", "Botha", "Pretorius", "Du Plessis"]

# --- Seeding Logic ---

async def clean_existing_demo_data(db: AsyncSession):
    print("Cleaning existing demo data for DHMS and MDVH...")
    # Wipe ALL benefit_balances first — the UNIQUE constraint is on
    # (member_id, benefit_category, benefit_year) without scheme_id, so reused
    # member IDs across scheme seeds (MedShield, DHMS, MDVH) cause IntegrityErrors.
    # This is a dev seed; full clear is the safest approach.
    await db.execute(delete(BenefitBalance))
    await db.commit()

    res = await db.execute(select(Scheme).where(Scheme.code.in_(["DHMS", "MDVH"])))
    schemes = res.scalars().all()
    for scheme in schemes:
        # SQLite doesn't always handle cascade well depending on pragmas, so we do it manually for safety
        scheme_id = scheme.id

        # Delete user memberships first to avoid FK violations when deleting users
        user_ids_res = await db.execute(select(User.id).where(User.scheme_id == scheme_id))
        user_ids = user_ids_res.scalars().all()
        if user_ids:
            await db.execute(delete(UserSchemeMembership).where(UserSchemeMembership.user_id.in_(user_ids)))

        # Delete BenefitLimits for this scheme's plans — must be done before
        # deleting PlanOptions to avoid orphaned rows reused on next seed when
        # SQLite recycles plan_option IDs.
        plan_ids_res = await db.execute(
            select(PlanOption.id).where(PlanOption.scheme_id == scheme_id)
        )
        plan_ids = plan_ids_res.scalars().all()
        if plan_ids:
            await db.execute(delete(BenefitLimit).where(BenefitLimit.plan_option_id.in_(plan_ids)))
            await db.execute(delete(ContributionRate).where(ContributionRate.plan_option_id.in_(plan_ids)))

        # Delete claims and lines
        claim_ids_res = await db.execute(select(Claim.id).where(Claim.scheme_id == scheme_id))
        claim_ids = claim_ids_res.scalars().all()
        if claim_ids:
            await db.execute(delete(ClaimLine).where(ClaimLine.claim_id.in_(claim_ids)))
            await db.execute(delete(Claim).where(Claim.id.in_(claim_ids)))

        # Delete members and related data
        member_ids_res = await db.execute(select(Member.id).where(Member.scheme_id == scheme_id))
        member_ids = member_ids_res.scalars().all()
        if member_ids:
            await db.execute(delete(Dependant).where(Dependant.member_id.in_(member_ids)))
            await db.execute(delete(MemberStatusHistory).where(MemberStatusHistory.member_id.in_(member_ids)))
            # Also delete authorisations if they exist
            auth_ids_res = await db.execute(select(Authorisation.id).where(Authorisation.member_id.in_(member_ids)))
            auth_ids = auth_ids_res.scalars().all()
            if auth_ids:
                await db.execute(delete(AuthorisationLine).where(AuthorisationLine.auth_id.in_(auth_ids)))
                await db.execute(delete(Authorisation).where(Authorisation.id.in_(auth_ids)))
            
            await db.execute(delete(Member).where(Member.id.in_(member_ids)))

        await db.execute(delete(User).where(User.scheme_id == scheme_id))
        await db.execute(delete(PlanOption).where(PlanOption.scheme_id == scheme_id))
        await db.execute(delete(SchemeTheme).where(SchemeTheme.scheme_id == scheme_id))
        await db.delete(scheme)
    await db.flush()

async def seed_global_reference_data(db: AsyncSession):
    print("Ensuring global reference data exists...")
    # ICD10, Tariff, and Rejection codes are usually shared. 
    # Checking if they exist, otherwise seeding a basic set.
    res = await db.execute(select(ICD10Code).limit(1))
    if not res.scalar():
        print("Seeding ICD10 codes...")
        icd10_data = [
            ("I10", "Essential (primary) hypertension", True),
            ("E11.9", "Type 2 diabetes mellitus without complications", True),
            ("J45.9", "Asthma, unspecified", True),
            ("M54.5", "Low back pain", False),
            ("J00", "Acute nasopharyngitis", False)
        ]
        for code, desc, pmb in icd10_data:
            db.add(ICD10Code(code=code, description=desc, is_pmb=pmb))
    
    res = await db.execute(select(TariffCode).limit(1))
    if not res.scalar():
        print("Seeding Tariff codes...")
        tariff_data = [
            ("0190", "GP Consultation", 45600, "GP"),
            ("0201", "Specialist Consultation", 87500, "SPEC"),
            ("1000", "Hospital Ward Day", 320000, "HOSP")
        ]
        for code, desc, rate, disc in tariff_data:
            db.add(TariffCode(code=code, description=desc, nhrpl_rate=rate, discipline_code=disc))
            
    res = await db.execute(select(RejectionCode).limit(1))
    if not res.scalar():
        print("Seeding Rejection codes...")
        rej_data = [
            ("BE01", "Benefit exhausted", "Benefit"),
            ("NC01", "Not covered", "Coverage")
        ]
        for code, desc, cat in rej_data:
            db.add(RejectionCode(code=code, description=desc, category=cat))
    await db.flush()

async def seed_scheme(db: AsyncSession, name, code, reg, domain, palette, plans_data):
    print(f"Seeding Scheme: {name} ({code})...")
    scheme = Scheme(name=name, code=code, registration_number=reg, is_active=True)
    db.add(scheme)
    await db.flush()

    # Theme
    db.add(SchemeTheme(scheme_id=scheme.id, palette=palette))
    
    # Plans
    plans = []
    for p_name, p_code, premium, h_net, d2d, multiplier in plans_data:
        plan = PlanOption(
            scheme_id=scheme.id, name=p_name, code=p_code, 
            monthly_premium=premium, hospital_network=h_net, 
            day_to_day_type=d2d, benefit_year=2026, tariff_multiplier=multiplier
        )
        db.add(plan)
        plans.append(plan)
    await db.flush()

    # Contribution Rates
    for plan in plans:
        for m_type, factor in [("PRINCIPAL", 1.0), ("ADULT_DEPENDANT", 0.8), ("CHILD", 0.3)]:
            db.add(ContributionRate(
                plan_option_id=plan.id,
                member_type=m_type,
                monthly_rate_cents=int(plan.monthly_premium * factor),
                effective_year=2026
            ))
            
    # Benefit Limits (Template)
    for plan in plans:
        limits = [
            ("hospital", "RAND", 100000000),
            ("gp_visits", "VISITS", 10),
            ("dentistry", "RAND", 500000)
        ]
        for cat, ltype, lval in limits:
            db.add(BenefitLimit(
                plan_option_id=plan.id,
                benefit_category=cat,
                limit_type=ltype,
                limit_value=lval,
                benefit_year=2026
            ))
    await db.flush()

    # Users
    password_hash = get_password_hash(f"{code}@1234")
    roles = ["super_admin", "scheme_admin", "claims_processor", "authorisation_officer"]
    for role in roles:
        email = f"{role.replace('_','')}@{domain}"
        db.add(User(
            email=email, full_name=f"{code} {role.title()}",
            hashed_password=password_hash, role=role, 
            scheme_id=scheme.id, is_active=True
        ))
    await db.flush()

    # Members (10 per scheme for brevity but sufficient for demo)
    print(f"Creating 10 members for {code}...")
    members = []
    for i in range(10):
        gender = random.choice(["male", "female"])
        fname = random.choice(SA_FIRST_NAMES_MALE if gender == "male" else SA_FIRST_NAMES_FEMALE)
        sname = random.choice(SA_SURNAMES)
        dob = random_dob(25, 55)
        
        member = Member(
            scheme_id=scheme.id,
            membership_number=f"{code}-{2026}-{i+1:06d}",
            id_number=generate_sa_id_number(dob, gender),
            first_name=fname,
            surname=sname,
            date_of_birth=dob,
            gender=gender,
            email=f"{fname.lower()}.{sname.lower()}@{domain}",
            cell_number=random_cell(),
            plan_option_id=random.choice(plans).id,
            status="active",
            join_date=date(2026, 1, 1)
        )
        db.add(member)
        members.append(member)
    await db.flush()

    # Initialise Benefit Balances
    for member in members:
        await initialise_benefit_balances(db, member.id, scheme.id, member.plan_option_id, 2026)
    
    # Sample Claims
    icd_res = await db.execute(select(ICD10Code).where(ICD10Code.is_active == True))
    icds = icd_res.scalars().all()
    tariff_res = await db.execute(select(TariffCode).where(TariffCode.is_active == True))
    tariffs = tariff_res.scalars().all()
    prov_res = await db.execute(select(Provider).limit(1))
    provider = prov_res.scalar()
    
    if not provider:
        provider = Provider(practice_number="PR12345", trading_name="Demo Clinic", is_active=True)
        db.add(provider)
        await db.flush()

    for i in range(5):
        member = random.choice(members)
        svc_from = date.today() - timedelta(days=random.randint(1, 30))
        claim = Claim(
            claim_number=f"CLM-{code}-{i+1:05d}",
            scheme_id=scheme.id,
            member_id=member.id,
            provider_id=provider.id,
            date_of_service_from=svc_from,
            date_of_service_to=svc_from,
            date_received=svc_from,
            claim_type="medical",
            status="approved",
            total_billed=10000,
            total_approved=10000,
            total_member_liability=0,
            total_scheme_liability=10000
        )
        db.add(claim)
        await db.flush()
        
        db.add(ClaimLine(
            claim_id=claim.id,
            tariff_code=random.choice(tariffs).code,
            description="Consultation",
            icd10_code=random.choice(icds).code,
            quantity=1,
            billed_amount=10000,
            approved_amount=10000
        ))
    
    await db.commit()

async def seed_tpa_user(db: AsyncSession):
    """Create one TPA admin user with access to both DHMS and MDVH for development."""
    res = await db.execute(select(Scheme).where(Scheme.code.in_(["DHMS", "MDVH"])))
    schemes = res.scalars().all()
    if len(schemes) < 2:
        print("Skipping TPA user seed — both DHMS and MDVH must exist first")
        return

    # Remove existing TPA user if present (re-seed safe)
    await db.execute(delete(User).where(User.email == "tpa@tpaadmin.co.za"))
    await db.flush()

    tpa_user = User(
        email="tpa@tpaadmin.co.za",
        full_name="TPA Administrator",
        hashed_password=get_password_hash("TPA@1234"),
        role="scheme_admin",
        scheme_id=schemes[0].id,  # primary scheme kept for backward compat
        is_active=True,
    )
    db.add(tpa_user)
    await db.flush()

    for scheme in schemes:
        db.add(UserSchemeMembership(user_id=tpa_user.id, scheme_id=scheme.id, is_active=True))
    await db.commit()
    print("TPA user created: tpa@tpaadmin.co.za (password: TPA@1234) — access to DHMS + MDVH")


async def main():
    async with AsyncSessionLocal() as db:
        await clean_existing_demo_data(db)
        await seed_global_reference_data(db)

        # Demo Health
        await seed_scheme(
            db, "Demo Health", "DHMS", "MS/DH/2026", "demohealth.co.za", "indigo",
            [
                ("Hospital Plan", "HOSP", 185000, "OPEN", "NONE", 100),
                ("Comprehensive", "COMP", 320000, "OPEN", "LIMIT", 100),
                ("Executive", "EXEC", 550000, "OPEN", "LIMIT", 200)
            ]
        )

        # MDV Health
        await seed_scheme(
            db, "MDV Health", "MDVH", "MS/MDV/2026", "mdvhealth.co.za", "teal",
            [
                ("Core Benefit", "CORE", 142000, "OPEN", "LIMIT", 100),
                ("Plus Option", "PLUS", 278000, "OPEN", "LIMIT", 100),
                ("Premier", "PREM", 480000, "OPEN", "LIMIT", 100)
            ]
        )

    async with AsyncSessionLocal() as db:
        await seed_tpa_user(db)

    print("\nSeed data created successfully!")
    print("Logins available for admin@demohealth.co.za and admin@mdvhealth.co.za")
    print("Password: [SCHEME]@1234 (e.g. DHMS@1234 or MDVH@1234)")
    print("TPA login: tpa@tpaadmin.co.za / TPA@1234 (access to DHMS + MDVH)")

if __name__ == "__main__":
    asyncio.run(main())
