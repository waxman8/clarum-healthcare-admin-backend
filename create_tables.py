from app.database import engine, Base  
import app.models  
import asyncio  
async def run():  
    async with engine.begin() as conn:  
        await conn.run_sync(Base.metadata.create_all)  
asyncio.run(run())  
