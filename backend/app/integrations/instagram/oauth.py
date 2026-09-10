import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

import httpx

from app.core.config import settings


INSTAGRAM_AUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH_URL = "https://graph.instagram.com/v24.0"


def create_oauth_state(
    user_id: int,
) -> str:
    """
    Create a signed OAuth state value containing the SocialPilot user ID.

    The state protects the OAuth callback from CSRF and allows the callback
    to identify the SocialPilot user after the browser returns from Instagram.
    """

    payload = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(16),
    }

    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")

    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return f"{encoded_payload}.{signature}"


def verify_oauth_state(
    state: str,
) -> int:
    """
    Verify an OAuth state value and return the SocialPilot user ID.
    """

    try:
        encoded_payload, signature = state.split(".", 1)

        expected_signature = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature,
        ):
            raise ValueError("Invalid Instagram OAuth state.")

        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload.encode("ascii")
            ).decode("utf-8")
        )

        user_id = int(payload["user_id"])

    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise ValueError(
            "Invalid Instagram OAuth state."
        ) from exc

    if user_id <= 0:
        raise ValueError(
            "Invalid Instagram OAuth user ID."
        )

    return user_id


def get_instagram_authorization_url(
    state: str,
) -> str:
    """
    Build the Instagram Login authorization URL.
    """

    if not settings.instagram_app_id:
        raise ValueError(
            "Instagram App ID is not configured."
        )

    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_redirect_uri,
        "response_type": "code",
        "scope": (
            "instagram_business_basic,"
            "instagram_business_content_publish"
        ),
        "state": state,
    }

    return f"{INSTAGRAM_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_access_token(
    code: str,
) -> dict:
    """
    Exchange an Instagram authorization code for an access token.
    """

    if not settings.instagram_app_id:
        raise ValueError(
            "Instagram App ID is not configured."
        )

    if not settings.instagram_app_secret:
        raise ValueError(
            "Instagram App Secret is not configured."
        )

    payload = {
        "client_id": settings.instagram_app_id,
        "client_secret": settings.instagram_app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": settings.instagram_redirect_uri,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            INSTAGRAM_TOKEN_URL,
            data=payload,
            headers={
                "Accept": "application/json",
            },
        )

    if response.is_error:
        raise httpx.HTTPStatusError(
            message=(
                "Instagram authorization code exchange failed: "
                f"{response.status_code} {response.text}"
            ),
            request=response.request,
            response=response,
        )

    return response.json()


async def get_long_lived_access_token(
    access_token: str,
) -> dict:
    """
    Exchange an Instagram access token for a long-lived token.
    """

    if not settings.instagram_app_secret:
        raise ValueError(
            "Instagram App Secret is not configured."
        )

    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.instagram_app_secret,
        "access_token": access_token,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{INSTAGRAM_GRAPH_URL}/access_token",
            params=params,
            headers={
                "Accept": "application/json",
            },
        )

    if response.is_error:
        raise httpx.HTTPStatusError(
            message=(
                "Instagram long-lived token exchange failed: "
                f"{response.status_code} {response.text}"
            ),
            request=response.request,
            response=response,
        )

    return response.json()