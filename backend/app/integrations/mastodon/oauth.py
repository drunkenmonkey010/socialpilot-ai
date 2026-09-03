from urllib.parse import urlencode

import httpx

from app.core.config import settings


MASTODON_AUTHORIZE_URL = (
    f"{settings.mastodon_instance_url}/oauth/authorize"
)

MASTODON_TOKEN_URL = (
    f"{settings.mastodon_instance_url}/oauth/token"
)

MASTODON_VERIFY_CREDENTIALS_URL = (
    f"{settings.mastodon_instance_url}/api/v1/accounts/verify_credentials"
)

MASTODON_STATUS_URL = (
    f"{settings.mastodon_instance_url}/api/v1/statuses"
)


def get_mastodon_authorization_url(state: str) -> str:
    """
    Build the Mastodon OAuth authorization URL.
    """

    if not settings.mastodon_client_id:
        raise ValueError(
            "Mastodon Client ID is not configured."
        )

    params = {
        "client_id": settings.mastodon_client_id,
        "redirect_uri": settings.mastodon_redirect_uri,
        "response_type": "code",
        "scope": "read:accounts write:statuses",
        "state": state,
    }

    return f"{MASTODON_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """
    Exchange the OAuth authorization code for a Mastodon access token.
    """

    if not settings.mastodon_client_id:
        raise ValueError(
            "Mastodon Client ID is not configured."
        )

    if not settings.mastodon_client_secret:
        raise ValueError(
            "Mastodon Client Secret is not configured."
        )

    payload = {
        "client_id": settings.mastodon_client_id,
        "client_secret": settings.mastodon_client_secret,
        "redirect_uri": settings.mastodon_redirect_uri,
        "grant_type": "authorization_code",
        "code": code,
        "scope": "read:accounts write:statuses",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MASTODON_TOKEN_URL,
            data=payload,
            headers={
                "Accept": "application/json",
            },
        )

    if response.is_error:
        raise RuntimeError(
            "Mastodon token exchange failed: "
            f"{response.status_code} {response.text}"
        )

    return response.json()


async def get_mastodon_account(
    access_token: str,
) -> dict:
    """
    Retrieve the currently authenticated Mastodon account.
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            MASTODON_VERIFY_CREDENTIALS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    if response.is_error:
        raise RuntimeError(
            "Mastodon account lookup failed: "
            f"{response.status_code} {response.text}"
        )

    return response.json()


async def publish_mastodon_status(
    access_token: str,
    content: str,
) -> dict:
    """
    Publish a text status to Mastodon.

    Returns the Mastodon status object returned by the API.
    """

    if not access_token:
        raise ValueError(
            "Mastodon access token is required."
        )

    if not content.strip():
        raise ValueError(
            "Mastodon status content cannot be empty."
        )

    payload = {
        "status": content,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MASTODON_STATUS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    if response.is_error:
        raise RuntimeError(
            "Mastodon status publication failed: "
            f"{response.status_code} {response.text}"
        )

    return response.json()