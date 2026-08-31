import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from api.config import settings
from api.db.models import Base
from typing import AsyncGenerator

logger = logging.getLogger("echo.db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db():
    """Initializes the database schema with automatic fallback if Postgres is unavailable."""
    global engine, AsyncSessionLocal

    try:
        async with engine.begin() as conn:
            if "postgresql" in str(engine.url):
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                except Exception as e:
                    logger.warning(f"Vector extension notice: {e}")
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Connected to primary database: {engine.url.render_as_string(hide_password=True)}")
    except Exception as pg_err:
        logger.warning(
            f"Could not connect to PostgreSQL ({pg_err}). Falling back to local SQLite memory store (sqlite+aiosqlite:///echo_memory.db)."
        )
        sqlite_url = "sqlite+aiosqlite:///echo_memory.db"
        engine = create_async_engine(sqlite_url, echo=False, future=True)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized successfully.")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
