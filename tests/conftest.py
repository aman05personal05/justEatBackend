"""
pytest conftest – spins up a test PostgreSQL database, creates all tables once
per session, and clears rows between every test for full isolation.

Set TEST_DATABASE_URL to override the default connection string.
"""
import os
import asyncio

from dotenv import load_dotenv
load_dotenv()

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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
    "postgresql+asyncpg://postgres:Aman%238130@localhost:5432/justeats_test",
)

# Connection parameters for database management
_pg_user = "postgres"
_pg_pass = "Aman#8130"  # Use plain password for asyncpg (not URL-encoded)
_pg_host = "localhost"
_pg_port = 5432
_test_db = "justeats_test"


def get_event_loop():
    """Get or create an event loop."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.new_event_loop()


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """Create the test DB if it doesn't exist, drop it after the session."""

    async def _create():
        conn = await asyncpg.connect(
            user=_pg_user,
            password=_pg_pass,
            host=_pg_host,
            port=_pg_port,
            database="postgres",
        )
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", _test_db
            )
            if not exists:
                await conn.execute(f'CREATE DATABASE "{_test_db}"')
        finally:
            await conn.close()

    async def _drop():
        conn = await asyncpg.connect(
            user=_pg_user,
            password=_pg_pass,
            host=_pg_host,
            port=_pg_port,
            database="postgres",
        )
        try:
            # Terminate any open connections first
            await conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1 AND pid <> pg_backend_pid()
                """,
                _test_db,
            )
            await conn.execute(f'DROP DATABASE IF EXISTS "{_test_db}"')
        finally:
            await conn.close()

    loop = get_event_loop()
    loop.run_until_complete(_create())
    yield
    loop.run_until_complete(_drop())


# ── Session-scoped engine: create tables once, drop after the full run ────────


@pytest_asyncio.fixture(scope="session")
async def engine(create_test_database):
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
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
