import urllib.parse
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base

TEST_DATABASE_URL = settings.TEST_DATABASE_URL or f"{settings.DATABASE_URL}_test"

parsed_url = urllib.parse.urlparse(settings.DATABASE_URL)
BASE_DB_URL = f"{parsed_url.scheme}://{parsed_url.netloc}/postgres"
TEST_DB_NAME = TEST_DATABASE_URL.split("/")[-1]


async def ensure_test_database():
    """Create the test database if it doesn't exist."""
    temp_engine = create_async_engine(BASE_DB_URL, isolation_level="AUTOCOMMIT")
    async with temp_engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname='{TEST_DB_NAME}'")
        )
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await temp_engine.dispose()


engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create tables before the test session starts and drop them after."""
    await ensure_test_database()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Fixture that yields a database session and rolls back after each test,
    even if the service code calls session.commit().
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        yield session

        await session.close()
        await transaction.rollback()
