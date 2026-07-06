import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.auth import Scheme
from app.models.reference import PlanOption

async def main():
    async with AsyncSessionLocal() as db:
        s_result = await db.execute(select(Scheme).where(Scheme.code == 'MDVH'))
        s = s_result.scalar_one_or_none()
        if s:
            print(f'Scheme ID: {s.id}')
            p_result = await db.execute(select(PlanOption).where(PlanOption.scheme_id == s.id))
            plans = p_result.scalars().all()
            print(f'Plans: {[{"id": pl.id, "code": pl.code} for pl in plans]}')
        else:
            print('MDVH not found')

if __name__ == "__main__":
    asyncio.run(main())
