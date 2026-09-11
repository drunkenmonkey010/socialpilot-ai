from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint reports that the application is alive."""

    response = await client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "SocialPilot AI"
    assert "environment" in data


@pytest.mark.asyncio
async def test_version_endpoint(client):
    """Version endpoint returns the running application version."""

    response = await client.get("/version")

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "SocialPilot AI"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_uses_application_version(client):
    """Root endpoint uses the centralized application version."""

    response = await client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "SocialPilot AI"
    assert data["version"] == "0.1.0"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_readiness_endpoint_reports_database_and_redis(
    client,
):
    """Readiness endpoint confirms both required dependencies."""

    response = await client.get("/ready")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ready"
    assert data["service"] == "SocialPilot AI"
    assert data["checks"]["database"] == "ready"
    assert data["checks"]["redis"] == "ready"


@pytest.mark.asyncio
async def test_readiness_fails_when_redis_is_unavailable(
    client,
):
    """Readiness returns 503 when Redis is unavailable."""

    with patch(
        "app.main.redis_queue.ping",
        new=AsyncMock(
            side_effect=ConnectionError("Redis unavailable")
        ),
    ):
        response = await client.get("/ready")

    assert response.status_code == 503

    data = response.json()

    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "ready"
    assert data["checks"]["redis"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_fails_when_database_is_unavailable(
    client,
):
    """Readiness returns 503 when PostgreSQL is unavailable."""

    mock_connection = MagicMock()

    mock_connection.__aenter__ = AsyncMock(
        side_effect=ConnectionError("Database unavailable")
    )
    mock_connection.__aexit__ = AsyncMock(
        return_value=False
    )

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connection

    with patch(
        "app.main.engine",
        mock_engine,
    ):
        response = await client.get("/ready")

    assert response.status_code == 503

    data = response.json()

    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "unavailable"
    assert data["checks"]["redis"] == "ready"


@pytest.mark.asyncio
async def test_operational_endpoints_do_not_require_authentication(
    client,
):
    """Operational endpoints must remain publicly probeable."""

    for path in (
        "/health",
        "/ready",
        "/version",
    ):
        response = await client.get(path)

        assert response.status_code in (200, 503)
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_readiness_does_not_expose_dependency_details(
    client,
):
    """Readiness responses expose status, not connection credentials."""

    response = await client.get("/ready")

    data = response.json()

    response_text = str(data).lower()

    assert "password" not in response_text
    assert "secret" not in response_text
    assert "token" not in response_text
    assert "postgresql://" not in response_text
    assert "redis://" not in response_text
