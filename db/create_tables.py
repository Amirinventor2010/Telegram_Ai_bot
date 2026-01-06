import asyncio
from dotenv import load_dotenv

load_dotenv()

from config.database import engine
from db.models import Base

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

if __name__ == "__main__":
    asyncio.run(main())
