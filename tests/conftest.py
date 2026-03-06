from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base

# Use the provided DATABASE_URL for tests
TEST_DATABASE_URL = settings.DATABASE_URL

# Use NullPool for tests to avoid connection stay-alive issues
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create tables before the test session starts and drop them after."""
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
        # Start the outer transaction
        transaction = await connection.begin()

        # Create a session bound to this connection
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        yield session

        # Roll back the outer transaction to undo all commits made during the test
        await session.close()
        await transaction.rollback()
