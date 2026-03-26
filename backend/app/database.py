import logging
import traceback
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

# Create Async Engine
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_kwargs = {
    "echo": False,
    "future": True,
}

if is_sqlite:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 50
    engine_kwargs["pool_timeout"] = 30
    engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Central Base class for all ORM models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency to get an isolated DB AsyncSession.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}\n{traceback.format_exc()}")
            await session.rollback()
            raise
        finally:
            await session.close()
