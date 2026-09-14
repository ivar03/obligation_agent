import os

# Isolate the suite from whatever is in a developer's .env BEFORE any app module
# is imported. Environment variables outrank .env in pydantic-settings, so these
# win. Without them a populated .env makes the suite call real LLM APIs and makes
# the webhook tests fail on signature/token checks they were written without.
os.environ["LLM_PROVIDER"] = "mock"
for _unset in (
    "GEMINI_API_KEY",
    "GMAIL_PUBSUB_VERIFICATION_TOKEN",
    "GOOGLE_CALENDAR_WEBHOOK_SECRET",
    "SLACK_SIGNING_SECRET",
    "JIRA_WEBHOOK_SECRET",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GOOGLE_CALENDAR_CLIENT_ID",
    "GOOGLE_CALENDAR_CLIENT_SECRET",
):
    os.environ[_unset] = ""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from app.main import app

# Test database in memory
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
