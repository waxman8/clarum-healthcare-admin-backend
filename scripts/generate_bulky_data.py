import asyncio
import random
import json
import os
import sys
from datetime import date, datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, func

from app.database import AsyncSessionLocal
from app.models.auth import Scheme, User
from app.models.reference import ICD10Code, TariffCode, PlanOption
from app.models.members import Member, Dependant, MemberStatusHistory
from app.models.providers import Provider
from app.models.authorisations import Authorisation, AuthorisationLine
from app.models.claims import Claim, ClaimLine

# Configuration
MEMBER_COUNT = 10000
AUTH_COUNT = 2000
CLAIM_COUNT = 4000
BATCH_SIZE = 500
SCHEME_CODE = "MDVH"

# Demographic data from seed_mdv.py
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

def random_cell():
    prefixes = ["071", "072", "073", "074", "076", "078", "079", "081", "082", "083", "084"]
    return f"{random.choice(prefixes)}{random.randint(1000000, 9999999)}"

def random_dob(min_age: int = 18, max_age: int = 65) -> date:
    today = date.today()
    age = random.randint(min_age, max_age)
    days_offset = random.randint(0, 364)
    return today - timedelta(days=age * 365 + days_offset)

class BulkyDataGenerator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scheme = None
        self.plans = []
        self.providers = []
        self.icd10s = []
        self.tariffs = []
        self.users = []
        
        # Track generated IDs for later use in auths/claims
        self.member_ids = []
        self.dependant_ids_map = {} # member_id -> [dependant_id, ...]
        self.all_beneficiaries = [] # List of (member_id, dependant_id or None)

    async def initialize(self):
        from app.config import settings
        print(f"Using DATABASE_URL: {settings.DATABASE_URL}")
        print(f"Initializing generator for {SCHEME_CODE}...")
        s_result = await self.db.execute(select(Scheme).where(Scheme.code == SCHEME_CODE))
        self.scheme = s_result.scalar_one_or_none()
        if not self.scheme:
            raise ValueError(f"Scheme {SCHEME_CODE} not found. Please run seed_mdv.py first.")
        
        p_result = await self.db.execute(select(PlanOption).where(PlanOption.scheme_id == self.scheme.id))
        self.plans = p_result.scalars().all()
        
        pr_result = await self.db.execute(select(Provider).where(Provider.is_active == True))
        self.providers = pr_result.scalars().all()
        
        icd_result = await self.db.execute(select(ICD10Code).where(ICD10Code.is_active == True))
        self.icd10s = icd_result.scalars().all()
        
        t_result = await self.db.execute(select(TariffCode).where(TariffCode.is_active == True))
        self.tariffs = t_result.scalars().all()
        
        u_result = await self.db.execute(select(User).where(User.scheme_id == self.scheme.id))
        self.users = u_result.scalars().all()
        
        print(f"Loaded: {len(self.plans)} plans, {len(self.providers)} providers, {len(self.icd10s)} ICD10s, {len(self.tariffs)} tariffs, {len(self.users)} users.")

    async def generate_members(self):
        print(f"Generating {MEMBER_COUNT} members...")
        
        # Get current highest sequence for membership number to avoid collisions
        # membership_number format: MDVH-2026-XXXXXX
        year = date.today().year
        prefix = f"{SCHEME_CODE}-{year}-"
        
        # Simple count for sequence
        # Start bulky data at a much higher sequence to avoid conflicts with demo data
        start_seq = 200000
        
        member_dicts = []
        for i in range(MEMBER_COUNT):
            gender = random.choice(["male", "female"])
            first_name = random.choice(MDV_FIRST_NAMES_MALE if gender == "male" else MDV_FIRST_NAMES_FEMALE)
            surname = random.choice(MDV_SURNAMES)
            dob = random_dob(20, 64)
            id_num = generate_sa_id_number(dob, gender)
            plan = random.choice(self.plans)
            
            join_date = date.today() - timedelta(days=random.randint(30, 1000))
            membership_num = f"{prefix}{start_seq + i:06d}"
            
            clean_surname = surname.lower().replace(' ', '').replace("'", '')
            email = f"{first_name.lower()[:3]}{clean_surname}{i}@{random.choice(['gmail.com', 'outlook.com', 'mdv-corp.za'])}"
            
            member_dicts.append({
                "scheme_id": self.scheme.id,
                "membership_number": membership_num,
                "id_number": id_num,
                "first_name": first_name,
                "surname": surname,
                "date_of_birth": dob,
                "gender": gender,
                "email": email,
                "cell_number": random_cell(),
                "plan_option_id": plan.id,
                "status": "active",
                "join_date": join_date,
            })
            
            if len(member_dicts) >= BATCH_SIZE:
                await self._bulk_insert_members(member_dicts)
                member_dicts = []
                
        if member_dicts:
            await self._bulk_insert_members(member_dicts)

    async def _bulk_insert_members(self, dicts):
        result = await self.db.execute(insert(Member).returning(Member.id), dicts)
        new_ids = result.scalars().all()
        self.member_ids.extend(new_ids)
        # Also add them as potential beneficiaries (principal member)
        for mid in new_ids:
            self.all_beneficiaries.append((mid, None))
        print(f"  Inserted {len(new_ids)} members (Total: {len(self.member_ids)})")

    async def generate_dependants(self):
        print("Generating dependants for every other member...")
        # Every other member gets 2 dependants
        target_member_ids = self.member_ids[::2]
        print(f"Targeting {len(target_member_ids)} members for dependants.")
        
        dep_dicts = []
        for mid in target_member_ids:
            # Dependant 1: Spouse
            gender = random.choice(["male", "female"])
            first_name = random.choice(MDV_FIRST_NAMES_MALE if gender == "male" else MDV_FIRST_NAMES_FEMALE)
            dob = random_dob(20, 60)
            dep_dicts.append({
                "member_id": mid,
                "dependant_relationship": "spouse",
                "id_number": generate_sa_id_number(dob, gender),
                "first_name": first_name,
                "surname": random.choice(MDV_SURNAMES), # might differ or same, use random
                "date_of_birth": dob,
                "gender": gender,
                "status": "active",
                "dependant_code": "01"
            })
            
            # Dependant 2: Child
            gender = random.choice(["male", "female"])
            first_name = random.choice(MDV_FIRST_NAMES_MALE if gender == "male" else MDV_FIRST_NAMES_FEMALE)
            dob = random_dob(1, 18)
            dep_dicts.append({
                "member_id": mid,
                "dependant_relationship": "child",
                "id_number": generate_sa_id_number(dob, gender),
                "first_name": first_name,
                "surname": random.choice(MDV_SURNAMES),
                "date_of_birth": dob,
                "gender": gender,
                "status": "active",
                "dependant_code": "02"
            })
            
            if len(dep_dicts) >= BATCH_SIZE:
                await self._bulk_insert_dependants(dep_dicts)
                dep_dicts = []
                
        if dep_dicts:
            await self._bulk_insert_dependants(dep_dicts)

    async def _bulk_insert_dependants(self, dicts):
        result = await self.db.execute(insert(Dependant).returning(Dependant.id, Dependant.member_id), dicts)
        rows = result.all()
        for did, mid in rows:
            self.all_beneficiaries.append((mid, did))
        print(f"  Inserted {len(rows)} dependants")

    async def generate_authorisations(self):
        print(f"Generating {AUTH_COUNT} authorisations...")
        year = date.today().year
        prefix = f"{SCHEME_CODE}-{year}-"
        
        # Get start seq
        count_res = await self.db.execute(select(func.count(Authorisation.id)).where(Authorisation.auth_number.like(f"{prefix}%")))
        start_seq = count_res.scalar_one() + 100000 # Offset for bulky data
        
        auth_dicts = []
        admin_user = self.users[0] if self.users else None
        
        for i in range(AUTH_COUNT):
            mid, did = random.choice(self.all_beneficiaries)
            provider = random.choice(self.providers)
            
            icd_codes = [random.choice(self.icd10s).code for _ in range(random.randint(1, 2))]
            proc_codes = [random.choice(self.tariffs).code for _ in range(random.randint(1, 2))]
            
            status = random.choice(["approved", "pending", "declined", "approved", "approved"])
            created_at = datetime.now() - timedelta(days=random.randint(0, 60))
            
            auth_dicts.append({
                "auth_number": f"{prefix}{start_seq + i:08d}",
                "member_id": mid,
                "dependant_id": did,
                "requesting_provider_id": provider.id,
                "icd10_codes": json.dumps(icd_codes),
                "procedure_codes": json.dumps(proc_codes),
                "auth_type": random.choice(["elective", "emergency", "chronic", "specialist_referral"]),
                "status": status,
                "approved_days": random.randint(1, 5) if status == "approved" else None,
                "clinical_notes": "Bulky data generation.",
                "created_by": admin_user.id if admin_user else None,
                "created_at": created_at,
            })
            
            if len(auth_dicts) >= BATCH_SIZE:
                await self.db.execute(insert(Authorisation), auth_dicts)
                auth_dicts = []
                print(f"  Inserted {BATCH_SIZE} auths...")

        if auth_dicts:
            await self.db.execute(insert(Authorisation), auth_dicts)
        print(f"Finished generating {AUTH_COUNT} authorisations.")

    async def generate_claims(self):
        print(f"Generating {CLAIM_COUNT} claims...")
        year_month = date.today().strftime('%Y%m')
        prefix = f"CLM-{SCHEME_CODE}-{year_month}-"
        
        count_res = await self.db.execute(select(func.count(Claim.id)).where(Claim.claim_number.like(f"{prefix}%")))
        start_seq = count_res.scalar_one() + 50000
        
        claim_dicts = []
        processor_user = next((u for u in self.users if u.role == 'claims_processor'), self.users[0] if self.users else None)
        
        for i in range(CLAIM_COUNT):
            mid, did = random.choice(self.all_beneficiaries)
            provider = random.choice(self.providers)
            
            status = random.choice(["paid", "approved", "partial", "rejected", "received", "paid"])
            total_billed = random.randint(20000, 500000) # cents
            
            dos = date.today() - timedelta(days=random.randint(1, 90))
            
            claim_dicts.append({
                "claim_number": f"{prefix}{start_seq + i:06d}",
                "scheme_id": self.scheme.id,
                "member_id": mid,
                "dependant_id": did,
                "provider_id": provider.id,
                "date_of_service_from": dos,
                "date_of_service_to": dos,
                "date_received": dos + timedelta(days=random.randint(0, 5)),
                "claim_type": random.choice(["medical", "hospital", "pharmacy"]),
                "status": status,
                "total_billed": total_billed,
                "total_approved": total_billed if status in ["paid", "approved"] else (total_billed // 2 if status == "partial" else 0),
                "total_member_liability": 0 if status in ["paid", "approved"] else (total_billed // 2 if status == "partial" else total_billed),
                "total_scheme_liability": total_billed if status in ["paid", "approved"] else (total_billed // 2 if status == "partial" else 0),
                "is_pmb": random.random() < 0.2,
                "adjudicated_by": processor_user.id if processor_user and status != "received" else None,
                "adjudicated_at": datetime.now() if status != "received" else None,
            })
            
            if len(claim_dicts) >= BATCH_SIZE:
                await self.db.execute(insert(Claim), claim_dicts)
                claim_dicts = []
                print(f"  Inserted {BATCH_SIZE} claims...")

        if claim_dicts:
            await self.db.execute(insert(Claim), claim_dicts)
        print(f"Finished generating {CLAIM_COUNT} claims.")

async def main():
    # Use AsyncSessionLocal which is already configured for the correct DB (Postgres/SQLite) from .env
    async with AsyncSessionLocal() as db:
        generator = BulkyDataGenerator(db)
        try:
            await generator.initialize()
            
            # Start transaction
            await generator.generate_members()
            await generator.generate_dependants()
            await generator.generate_authorisations()
            await generator.generate_claims()
            
            await db.commit()
            print("\nSUCCESS: Bulk data generation complete!")
            print(f"Created {MEMBER_COUNT} members, ~10000 dependants, {AUTH_COUNT} auths, {CLAIM_COUNT} claims.")
            
        except Exception as e:
            await db.rollback()
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
