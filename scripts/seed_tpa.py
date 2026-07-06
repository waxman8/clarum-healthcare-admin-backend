import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.models.auth import User, Scheme, UserSchemeMembership
from app.auth.security import get_password_hash
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {}
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def seed_tpa():
    async with AsyncSessionLocal() as db:
        print("Creating TPA Admin user...")
        
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == "tpa@tpaadmin.co.za"))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                email="tpa@tpaadmin.co.za",
                full_name="TPA Admin (Multi-Scheme)",
                hashed_password=get_password_hash("TPA@1234"),
                role="super_admin",
                is_active=True,
            )
            db.add(user)
            await db.flush()
        
        # Link to all active schemes
        schemes_result = await db.execute(select(Scheme).where(Scheme.is_active == True))
        schemes = schemes_result.scalars().all()
        
        for scheme in schemes:
            # Check if membership already exists
            m_result = await db.execute(
                select(UserSchemeMembership)
                .where(UserSchemeMembership.user_id == user.id)
                .where(UserSchemeMembership.scheme_id == scheme.id)
            )
            if not m_result.scalar_one_or_none():
                membership = UserSchemeMembership(
                    user_id=user.id,
                    scheme_id=scheme.id,
                    is_active=True
                )
                db.add(membership)
        
        await db.commit()
        print("TPA Admin user seeded and linked to all schemes.")

if __name__ == "__main__":
    asyncio.run(seed_tpa())
