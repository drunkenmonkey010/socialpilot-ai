from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.jwt import create_access_token


async def create_brand(client, headers, name="Security Test Brand"):
    response = await client.post(
        "/brands",
        headers=headers,
        json={
            "name": name,
            "description": "Security API test brand",
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_campaign(
    client,
    headers,
    brand_id,
):
    response = await client.post(
        "/campaigns",
        headers=headers,
        json={
            "brand_id": brand_id,
            "name": "Security Test Campaign",
            "description": "Security API test campaign",
        },
    )

    assert response.status_code == 201

    return response.json()


@pytest.mark.asyncio
async def test_malformed_jwt_is_rejected(client):
    """Malformed JWT credentials must be rejected."""

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer definitely-not-a-jwt",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_expired_jwt_is_rejected(client, test_user):
    """Expired JWT credentials must not authenticate a user."""

    token = create_access_token(
        subject=str(test_user["id"]),
        expires_delta=timedelta(seconds=-1),
    )

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_jwt_without_subject_is_rejected(client):
    """A JWT without a user subject must not authenticate."""

    token = jwt.encode(
        {
            "iat": 0,
            "exp": 4102444800,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_jwt_with_invalid_subject_is_rejected(client):
    """A JWT with a non-integer subject must be rejected."""

    token = create_access_token(
        subject="not-an-integer",
    )

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_jwt_for_nonexistent_user_is_rejected(client):
    """A validly signed JWT for an unknown user must be rejected."""

    token = create_access_token(
        subject="999999999",
    )

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_invalid_bearer_scheme_is_rejected(
    client,
    test_user,
):
    """Credentials must use the Bearer authentication scheme."""

    login_response = await client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me",
        headers={
            "Authorization": f"Basic {token}",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_brand_endpoint_requires_authentication(
    client,
):
    """Protected resource endpoints must require authentication."""

    response = await client.get("/brands")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_campaign_endpoint_requires_authentication(
    client,
):
    """Protected campaign endpoints must require authentication."""

    response = await client.get("/campaigns/brand/1")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_post_endpoint_requires_authentication(
    client,
):
    """Protected post endpoints must require authentication."""

    response = await client.get("/posts/1")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_social_account_endpoint_requires_authentication(
    client,
):
    """Protected social-account endpoints must require authentication."""

    response = await client.get("/social-accounts")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cross_user_campaign_access_is_rejected(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot access another user's campaign."""

    brand = await create_brand(
        client,
        auth_headers,
    )

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    response = await client.get(
        f"/campaigns/{campaign['id']}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_user_brand_access_is_rejected(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot access another user's brand."""

    brand = await create_brand(
        client,
        auth_headers,
    )

    response = await client.get(
        f"/brands/{brand['id']}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_validation_error_uses_standard_error_structure(
    client,
    auth_headers,
):
    """Invalid request bodies use the standardized error envelope."""

    response = await client.post(
        "/brands",
        headers=auth_headers,
        json={
            "unexpected_field": "invalid",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]


@pytest.mark.asyncio
async def test_request_id_is_generated_when_missing(
    client,
    auth_headers,
):
    """The API generates a request ID when one is not supplied."""

    response = await client.get(
        "/brands",
        headers=auth_headers,
    )

    assert response.status_code == 200

    request_id = response.headers.get("X-Request-ID")

    assert request_id
    assert len(request_id) > 10


@pytest.mark.asyncio
async def test_request_id_is_preserved(
    client,
    auth_headers,
):
    """The API preserves a caller-supplied request ID."""

    supplied_request_id = "security-test-request-id-123"

    response = await client.get(
        "/brands",
        headers={
            **auth_headers,
            "X-Request-ID": supplied_request_id,
        },
    )

    assert response.status_code == 200

    assert (
        response.headers.get("X-Request-ID")
        == supplied_request_id
    )


@pytest.mark.asyncio
async def test_social_account_response_never_exposes_tokens(
    client,
    auth_headers,
):
    """OAuth credentials must remain absent from API responses."""

    response = await client.post(
        "/social-accounts",
        headers=auth_headers,
        json={
            "platform": "mastodon",
            "account_name": "security-test",
            "account_id": "security-123",
            "access_token": "VERY-SECRET-ACCESS-TOKEN",
            "refresh_token": "VERY-SECRET-REFRESH-TOKEN",
            "is_active": True,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert "access_token" not in data
    assert "refresh_token" not in data

    response = await client.get(
        f"/social-accounts/{data['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" not in data
    assert "refresh_token" not in data

    response = await client.get(
        "/social-accounts",
        headers=auth_headers,
    )

    assert response.status_code == 200

    for account in response.json():
        assert "access_token" not in account
        assert "refresh_token" not in account


@pytest.mark.asyncio
async def test_mastodon_oauth_callback_does_not_return_credentials(
    client,
):
    """OAuth callback errors must not accidentally expose credentials."""

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "error": "access_denied",
            "error_description": "Authorization denied",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "access_token" not in str(data)
    assert "refresh_token" not in str(data)


@pytest.mark.asyncio
async def test_instagram_oauth_callback_does_not_return_credentials(
    client,
):
    """Instagram OAuth errors must not expose credentials."""

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "error": "access_denied",
            "error_description": "Authorization denied",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "access_token" not in str(data)
    assert "refresh_token" not in str(data)
