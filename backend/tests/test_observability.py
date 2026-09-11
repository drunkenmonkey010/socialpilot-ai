import logging

import pytest


@pytest.mark.asyncio
async def test_api_response_contains_request_id(client):
    """Every API response should expose the request correlation ID."""

    response = await client.get("/health")

    assert response.status_code == 200

    request_id = response.headers.get("X-Request-ID")

    assert request_id
    assert len(request_id) > 10


@pytest.mark.asyncio
async def test_api_preserves_client_request_id(client):
    """A supplied X-Request-ID should be preserved in the response."""

    request_id = "test-request-12345"

    response = await client.get(
        "/health",
        headers={
            "X-Request-ID": request_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.asyncio
async def test_api_generates_different_request_ids(client):
    """Requests without IDs should receive unique correlation IDs."""

    first_response = await client.get("/health")
    second_response = await client.get("/health")

    first_request_id = first_response.headers.get(
        "X-Request-ID"
    )
    second_request_id = second_response.headers.get(
        "X-Request-ID"
    )

    assert first_request_id
    assert second_request_id
    assert first_request_id != second_request_id


@pytest.mark.asyncio
async def test_api_request_is_logged(
    client,
    caplog,
):
    """Completed API requests should produce an observability log."""

    with caplog.at_level(
        logging.INFO,
        logger="socialpilot.api",
    ):
        response = await client.get(
            "/health",
            headers={
                "X-Request-ID": "observability-test-123",
            },
        )

    assert response.status_code == 200

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "socialpilot.api"
    ]

    assert any(
        "API request completed" in message
        and "request_id=observability-test-123" in message
        and "method=GET" in message
        and "path=/health" in message
        and "status=200" in message
        and "duration_ms=" in message
        for message in messages
    )


@pytest.mark.asyncio
async def test_standard_error_response_contains_request_id(
    client,
):
    """Standardized API errors should retain request correlation."""

    request_id = "error-request-67890"

    response = await client.get(
        "/auth/me",
        headers={
            "X-Request-ID": request_id,
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["X-Request-ID"] == request_id
