from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.api.routes import instagram as instagram_routes
from app.api.routes import mastodon as mastodon_routes
from app.core.config import settings


async def create_social_account(
    client,
    headers,
    platform="mastodon",
    account_name="test-account",
    account_id="external-123",
):
    response = await client.post(
        "/social-accounts",
        headers=headers,
        json={
            "platform": platform,
            "account_name": account_name,
            "account_id": account_id,
            "access_token": "super-secret-access-token",
            "refresh_token": "super-secret-refresh-token",
            "is_active": True,
        },
    )

    assert response.status_code == 201

    return response.json()


@pytest.mark.asyncio
async def test_social_account_create_excludes_oauth_tokens(
    client,
    auth_headers,
):
    """Social-account API responses must never expose OAuth credentials."""

    account = await create_social_account(
        client,
        auth_headers,
    )

    assert account["platform"] == "mastodon"
    assert account["account_name"] == "test-account"
    assert account["account_id"] == "external-123"

    assert "access_token" not in account
    assert "refresh_token" not in account


@pytest.mark.asyncio
async def test_social_account_crud(
    client,
    auth_headers,
):
    """A user can create, retrieve, update, list, and delete an account."""

    account = await create_social_account(
        client,
        auth_headers,
    )

    account_id = account["id"]

    response = await client.get(
        f"/social-accounts/{account_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == account_id

    response = await client.get(
        "/social-accounts",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert any(
        item["id"] == account_id
        for item in response.json()
    )

    response = await client.patch(
        f"/social-accounts/{account_id}",
        headers=auth_headers,
        json={
            "account_name": "updated-account",
            "is_active": False,
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["account_name"] == "updated-account"
    assert updated["is_active"] is False
    assert "access_token" not in updated
    assert "refresh_token" not in updated

    response = await client.delete(
        f"/social-accounts/{account_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    response = await client.get(
        f"/social-accounts/{account_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_social_account_cannot_be_accessed_by_another_user(
    client,
    auth_headers,
    second_auth_headers,
):
    """Social accounts are isolated between users."""

    account = await create_social_account(
        client,
        auth_headers,
    )

    account_id = account["id"]

    response = await client.get(
        f"/social-accounts/{account_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/social-accounts/{account_id}",
        headers=second_auth_headers,
        json={
            "account_name": "unauthorized-update",
        },
    )

    assert response.status_code == 404

    response = await client.delete(
        f"/social-accounts/{account_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_social_accounts_require_authentication(client):
    """Social-account endpoints require authentication."""

    response = await client.get("/social-accounts")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_mastodon_connect_requires_authentication(client):
    """Mastodon OAuth initiation requires an authenticated user."""

    response = await client.get(
        "/social-accounts/mastodon/connect",
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_mastodon_connect_rejects_missing_configuration(
    client,
    auth_headers,
    monkeypatch,
):
    """Mastodon OAuth cannot start without required configuration."""

    monkeypatch.setattr(
        settings,
        "mastodon_client_id",
        None,
    )

    response = await client.get(
        "/social-accounts/mastodon/connect",
        headers=auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_mastodon_connect_returns_oauth_redirect(
    client,
    auth_headers,
    monkeypatch,
):
    """Mastodon OAuth initiation returns a signed state in the redirect."""

    monkeypatch.setattr(
        settings,
        "mastodon_client_id",
        "test-client-id",
    )

    monkeypatch.setattr(
        settings,
        "mastodon_client_secret",
        "test-client-secret",
    )

    monkeypatch.setattr(
        mastodon_routes,
        "get_mastodon_authorization_url",
        lambda state: (
            "https://mastodon.example/oauth/authorize"
            f"?state={state}&client_id=test-client-id"
        ),
    )

    response = await client.get(
        "/social-accounts/mastodon/connect",
        headers=auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 307

    location = response.headers["location"]

    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert "state" in query

    state = query["state"][0]

    assert state

    verified_user_id = mastodon_routes._verify_oauth_state(state)

    assert verified_user_id > 0


@pytest.mark.asyncio
async def test_mastodon_callback_requires_code(client):
    """Mastodon callback rejects requests without an authorization code."""

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "state": "invalid-state",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mastodon_callback_requires_state(client):
    """Mastodon callback rejects requests without OAuth state."""

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "code": "test-code",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mastodon_callback_rejects_invalid_state(client):
    """Mastodon callback rejects forged OAuth state."""

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "code": "test-code",
            "state": "forged-state",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mastodon_callback_handles_provider_error(client):
    """Provider-side OAuth errors are returned as client errors."""

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "error": "access_denied",
            "error_description": "User denied access",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["error"]["code"] == "BAD_REQUEST"
    assert data["error"]["message"] == "User denied access"


@pytest.mark.asyncio
async def test_mastodon_callback_creates_account(
    client,
    test_user,
    monkeypatch,
):
    """A successful Mastodon callback creates a safe social-account record."""

    state = mastodon_routes._create_oauth_state(
        test_user["id"],
    )

    async def fake_exchange_code(code):
        assert code == "mastodon-test-code"

        return {
            "access_token": "mastodon-access-secret",
            "refresh_token": "mastodon-refresh-secret",
        }

    async def fake_get_account(access_token):
        assert access_token == "mastodon-access-secret"

        return {
            "id": "mastodon-987",
            "username": "testuser",
            "acct": "testuser@example.social",
        }

    monkeypatch.setattr(
        mastodon_routes,
        "exchange_code_for_token",
        fake_exchange_code,
    )

    monkeypatch.setattr(
        mastodon_routes,
        "get_mastodon_account",
        fake_get_account,
    )

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "code": "mastodon-test-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "connected"
    assert data["account"]["platform"] == "mastodon"
    assert data["account"]["account_id"] == "mastodon-987"
    assert data["account"]["account_name"] == "testuser@example.social"
    assert data["account"]["is_active"] is True

    assert "access_token" not in data
    assert "refresh_token" not in data
    assert "access_token" not in data["account"]
    assert "refresh_token" not in data["account"]


@pytest.mark.asyncio
async def test_mastodon_callback_reconnects_existing_account(
    client,
    test_user,
    monkeypatch,
):
    """A repeated Mastodon OAuth connection updates the existing account."""

    state = mastodon_routes._create_oauth_state(
        test_user["id"],
    )

    first_token = "mastodon-first-token"
    second_token = "mastodon-second-token"

    call_count = 0

    async def fake_exchange_code(code):
        nonlocal call_count

        call_count += 1

        if call_count == 1:
            return {
                "access_token": first_token,
                "refresh_token": "first-refresh",
            }

        return {
            "access_token": second_token,
            "refresh_token": "second-refresh",
        }

    async def fake_get_account(access_token):
        return {
            "id": "mastodon-same-account",
            "username": "testuser",
            "acct": "testuser@example.social",
        }

    monkeypatch.setattr(
        mastodon_routes,
        "exchange_code_for_token",
        fake_exchange_code,
    )

    monkeypatch.setattr(
        mastodon_routes,
        "get_mastodon_account",
        fake_get_account,
    )

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "code": "first-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    first_account = response.json()["account"]

    response = await client.get(
        "/social-accounts/mastodon/callback",
        params={
            "code": "second-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    second_account = response.json()["account"]

    assert second_account["id"] == first_account["id"]
    assert second_account["account_id"] == "mastodon-same-account"

    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_instagram_connect_requires_authentication(client):
    """Instagram OAuth initiation requires authentication."""

    response = await client.get(
        "/social-accounts/instagram/connect",
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_instagram_connect_rejects_missing_configuration(
    client,
    auth_headers,
    monkeypatch,
):
    """Instagram OAuth cannot start without its application ID."""

    monkeypatch.setattr(
        settings,
        "instagram_app_id",
        None,
    )

    response = await client.get(
        "/social-accounts/instagram/connect",
        headers=auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_instagram_connect_returns_oauth_redirect(
    client,
    auth_headers,
    monkeypatch,
):
    """Instagram OAuth initiation returns a redirect with state."""

    monkeypatch.setattr(
        settings,
        "instagram_app_id",
        "test-instagram-app-id",
    )

    monkeypatch.setattr(
        instagram_routes,
        "get_instagram_authorization_url",
        lambda state: (
            "https://instagram.example/oauth/authorize"
            f"?state={state}&client_id=test-instagram-app-id"
        ),
    )

    response = await client.get(
        "/social-accounts/instagram/connect",
        headers=auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 307

    location = response.headers["location"]

    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert "state" in query
    assert query["state"][0]


@pytest.mark.asyncio
async def test_instagram_callback_requires_code(client):
    """Instagram callback rejects requests without an authorization code."""

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "state": "invalid-state",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_instagram_callback_requires_state(client):
    """Instagram callback rejects requests without OAuth state."""

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "code": "test-code",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_instagram_callback_rejects_invalid_state(client):
    """Instagram callback rejects forged OAuth state."""

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "code": "test-code",
            "state": "forged-state",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_instagram_callback_handles_provider_error(client):
    """Instagram provider-side OAuth errors are handled safely."""

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "error": "access_denied",
            "error_description": "User denied access",
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["error"]["code"] == "BAD_REQUEST"
    assert data["error"]["message"] == "User denied access"


@pytest.mark.asyncio
async def test_instagram_callback_creates_account(
    client,
    test_user,
    monkeypatch,
):
    """A successful Instagram OAuth callback creates an account safely."""

    state = instagram_routes.create_oauth_state(
        user_id=test_user["id"],
    )

    async def fake_exchange_code(code):
        assert code == "instagram-test-code"

        return {
            "access_token": "instagram-short-lived-token",
        }

    async def fake_long_lived_token(access_token):
        assert access_token == "instagram-short-lived-token"

        return {
            "access_token": "instagram-long-lived-secret",
            "expires_in": 3600,
        }

    class FakeInstagramClient:
        def __init__(self, access_token):
            assert access_token == "instagram-long-lived-secret"

        async def get_account(self):
            return {
                "id": "instagram-123",
                "username": "testinstagram",
            }

    monkeypatch.setattr(
        instagram_routes,
        "exchange_code_for_access_token",
        fake_exchange_code,
    )

    monkeypatch.setattr(
        instagram_routes,
        "get_long_lived_access_token",
        fake_long_lived_token,
    )

    monkeypatch.setattr(
        instagram_routes,
        "InstagramClient",
        FakeInstagramClient,
    )

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "code": "instagram-test-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "connected"
    assert data["platform"] == "instagram"
    assert data["account_id"] == "instagram-123"
    assert data["account_name"] == "testinstagram"

    assert "access_token" not in data
    assert "refresh_token" not in data


@pytest.mark.asyncio
async def test_instagram_callback_reconnects_existing_account(
    client,
    test_user,
    monkeypatch,
):
    """Repeated Instagram OAuth connections update the same account."""

    state = instagram_routes.create_oauth_state(
        user_id=test_user["id"],
    )

    call_count = 0

    async def fake_exchange_code(code):
        nonlocal call_count

        call_count += 1

        return {
            "access_token": f"short-token-{call_count}",
        }

    async def fake_long_lived_token(access_token):
        return {
            "access_token": f"long-token-{call_count}",
            "expires_in": 3600,
        }

    class FakeInstagramClient:
        def __init__(self, access_token):
            pass

        async def get_account(self):
            return {
                "id": "instagram-same-account",
                "username": "sameinstagram",
            }

    monkeypatch.setattr(
        instagram_routes,
        "exchange_code_for_access_token",
        fake_exchange_code,
    )

    monkeypatch.setattr(
        instagram_routes,
        "get_long_lived_access_token",
        fake_long_lived_token,
    )

    monkeypatch.setattr(
        instagram_routes,
        "InstagramClient",
        FakeInstagramClient,
    )

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "code": "first-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    first_account = response.json()

    response = await client.get(
        "/social-accounts/instagram/callback",
        params={
            "code": "second-code",
            "state": state,
        },
    )

    assert response.status_code == 200

    second_account = response.json()

    assert second_account["account_id"] == "instagram-same-account"
    assert second_account["account_name"] == "sameinstagram"

    assert first_account["account_id"] == second_account["account_id"]

    assert "access_token" not in second_account
    assert "refresh_token" not in second_account
