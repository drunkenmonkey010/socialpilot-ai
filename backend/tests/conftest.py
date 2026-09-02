import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    """Provide an HTTP client connected directly to the FastAPI application."""

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def test_user():
    """Create a unique test user and remove it after the test."""

    email = f"pytest-{uuid.uuid4().hex}@example.com"
    password = "secret123"

    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        user_id = user.id

    yield {
        "id": user_id,
        "email": email,
        "password": password,
    }

    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(User).where(User.id == user_id)
        )
        await session.commit()

    await engine.dispose()