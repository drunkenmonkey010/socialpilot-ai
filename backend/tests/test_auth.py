import pytest


@pytest.mark.asyncio
async def test_login_returns_access_token(client, test_user):
    """A valid user should receive a JWT access token."""

    response = await client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["access_token"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(client, test_user):
    """An incorrect password should be rejected."""

    response = await client.post(
        "/auth/login",
        json={
            "email": test_user["email"],
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_me_requires_authentication(client):
    """The /auth/me endpoint should require a valid JWT."""

    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_authenticated_user(client, test_user):
    """A valid JWT should identify the authenticated user."""

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
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == test_user["id"]
    assert data["email"] == test_user["email"]
    assert data["is_active"] is True