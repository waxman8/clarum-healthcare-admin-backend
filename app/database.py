from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.engine import make_url
from app.config import settings

# Parse URL and handle sslmode for asyncpg
url = make_url(settings.DATABASE_URL)
_connect_args = {}

if settings.is_sqlite:
    _connect_args["check_same_thread"] = False
else:
    # Handle sslmode: asyncpg uses 'ssl' keyword in connect_args
    if "sslmode" in url.query:
        query = dict(url.query)
        sslmode = query.pop("sslmode")
        url = url.set(query=query)
        if sslmode in ("require", "verify-ca", "verify-full"):
            _connect_args["ssl"] = True
    else:
        # Default for Neon/Vercel
        _connect_args["ssl"] = True

engine = create_async_engine(
    url,
    connect_args=_connect_args,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
