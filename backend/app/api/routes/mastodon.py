import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.integrations.mastodon.oauth import (
    exchange_code_for_token,
    get_mastodon_account,
    get_mastodon_authorization_url,
)
from app.models.user import User
from app.repositories.social_account import SocialAccountRepository
from app.schemas.social_account import SocialAccountCreate
from app.services.social_account import SocialAccountService


router = APIRouter(
    prefix="/social-accounts/mastodon",
    tags=["Mastodon"],
)


STATE_EXPIRATION_SECONDS = 600


def _create_oauth_state(user_id: int) -> str:
    """
    Create a signed OAuth state containing the SocialPilot user ID.

    The state is:
        base64url(payload).signature
    """

    payload = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + STATE_EXPIRATION_SECONDS,
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    encoded_payload = base64.urlsafe_b64encode(
        payload_bytes
    ).decode("utf-8").rstrip("=")

    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    encoded_signature = base64.urlsafe_b64encode(
        signature
    ).decode("utf-8").rstrip("=")

    return f"{encoded_payload}.{encoded_signature}"


def _verify_oauth_state(state: str) -> int:
    """
    Verify the OAuth state and return the SocialPilot user ID.
    """

    try:
        encoded_payload, encoded_signature = state.split(".", 1)

        expected_signature = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        provided_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )

        if not hmac.compare_digest(
            expected_signature,
            provided_signature,
        ):
            raise ValueError("Invalid state signature")

        payload_bytes = base64.urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )

        payload = json.loads(
            payload_bytes.decode("utf-8")
        )

        if int(payload["exp"]) < int(time.time()):
            raise ValueError("OAuth state has expired")

        user_id = int(payload["user_id"])

        return user_id

    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state.",
        )


@router.get("/connect")
async def connect_mastodon(
    current_user: User = Depends(get_current_user),
):
    """
    Start the Mastodon OAuth authorization flow.
    """

    if not settings.mastodon_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mastodon Client ID is not configured.",
        )

    if not settings.mastodon_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mastodon Client Secret is not configured.",
        )

    state = _create_oauth_state(
        current_user.id,
    )

    authorization_url = get_mastodon_authorization_url(
        state=state,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/callback")
async def mastodon_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Handle the Mastodon OAuth callback.

    Exchanges the authorization code for an access token,
    retrieves the Mastodon account, and saves the connection
    to the authenticated SocialPilot user.
    """

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is missing.",
        )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state is missing.",
        )

    # Recover and verify the SocialPilot user who initiated OAuth.
    user_id = _verify_oauth_state(state)

    try:
        # Exchange the temporary authorization code
        # for a permanent Mastodon access token.
        token_data = await exchange_code_for_token(
            code,
        )

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:
            raise RuntimeError(
                "Mastodon did not return an access token."
            )

        # Retrieve the Mastodon account associated
        # with the newly issued token.
        mastodon_account = await get_mastodon_account(
            access_token,
        )

        mastodon_account_id = mastodon_account.get(
            "id"
        )

        mastodon_username = mastodon_account.get(
            "username"
        )

        mastodon_acct = mastodon_account.get(
            "acct"
        )

        if not mastodon_account_id:
            raise RuntimeError(
                "Mastodon account ID was not returned."
            )

        if not mastodon_username:
            raise RuntimeError(
                "Mastodon username was not returned."
            )

        # Prefer the full Mastodon handle when available.
        account_name = (
            mastodon_acct
            or mastodon_username
        )

        # Check whether this Mastodon account is
        # already connected to this SocialPilot user.
        existing_account = (
            await SocialAccountRepository.get_by_platform_and_account_id(
                session,
                user_id,
                "mastodon",
                str(mastodon_account_id),
            )
        )

        if existing_account:
            # Refresh the access token if the account
            # was previously connected.
            existing_account.access_token = access_token
            existing_account.refresh_token = token_data.get(
                "refresh_token"
            )
            existing_account.is_active = True
            existing_account.account_name = account_name

            updated_account = (
                await SocialAccountRepository.update(
                    session,
                    existing_account,
                )
            )

            return {
                "status": "connected",
                "message": "Mastodon account reconnected successfully.",
                "account": {
                    "id": updated_account.id,
                    "platform": updated_account.platform,
                    "account_name": updated_account.account_name,
                    "account_id": updated_account.account_id,
                    "is_active": updated_account.is_active,
                },
            }

        # Create a brand-new SocialAccount connection.
        account_data = SocialAccountCreate(
            platform="mastodon",
            account_name=account_name,
            account_id=str(mastodon_account_id),
            access_token=access_token,
            refresh_token=token_data.get(
                "refresh_token"
            ),
            token_expires_at=None,
            is_active=True,
        )

        social_account = (
            await SocialAccountService.create_account(
                session,
                user_id,
                account_data,
            )
        )

        return {
            "status": "connected",
            "message": "Mastodon account connected successfully.",
            "account": {
                "id": social_account.id,
                "platform": social_account.platform,
                "account_name": social_account.account_name,
                "account_id": social_account.account_id,
                "is_active": social_account.is_active,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mastodon connection failed: {exc}",
        ) from exc