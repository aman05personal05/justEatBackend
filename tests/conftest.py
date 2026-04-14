"""
pytest conftest – spins up a test PostgreSQL database, creates all tables once
per session, and clears rows between every test for full isolation.

Set TEST_DATABASE_URL to override the default connection string.
"""
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Register every model with Base.metadata before create_all
import app.models.cart  # noqa: F401
import app.models.menu_item  # noqa: F401
import app.models.order  # noqa: F401
import app.models.refresh_token  # noqa: F401
import app.models.restaurant  # noqa: F401
import app.models.user  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/justeats_test",
)


# ── Session-scoped engine: create tables once, drop after the full run ────────


@pytest_asyncio.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


# ── Wipe every table after each test ─────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(engine):
    yield
    async with engine.begin() as conn:
        # Disable FK checks temporarily so we can truncate in any order
        await conn.execute(text("SET session_replication_role = replica"))
        for table in Base.metadata.sorted_tables:
            await conn.execute(table.delete())
        await conn.execute(text("SET session_replication_role = DEFAULT"))


# ── HTTP client with get_db overridden to use the test engine ─────────────────


@pytest_asyncio.fixture
async def client(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
