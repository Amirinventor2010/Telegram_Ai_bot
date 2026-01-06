from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from config import settings
from contextlib import asynccontextmanager
# Engine = connection pool
engine = create_async_engine(
    settings.db_url(),
    pool_size=10,          # برای شروع خوبه
    max_overflow=20,       # تحمل پیک
    pool_pre_ping=True,    # کانکشن‌های مرده رو تشخیص می‌ده
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def db_ping() -> None:
    """یه تست خیلی ساده برای اینکه بفهمیم DB زنده‌ست."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        yield session
