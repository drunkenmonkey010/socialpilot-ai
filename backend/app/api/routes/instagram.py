from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.integrations.instagram.client import InstagramClient
from app.integrations.instagram.oauth import (
    create_oauth_state,
    exchange_code_for_access_token,
    get_instagram_authorization_url,
    get_long_lived_access_token,
    verify_oauth_state,
)
from app.models.user import User
from app.schemas.social_account import (
    SocialAccountCreate,
    SocialAccountUpdate,
)
from app.services.social_account import SocialAccountService


router = APIRouter(
    prefix="/social-accounts/instagram",
    tags=["Instagram"],
)


@router.get("/connect")
async def connect_instagram(
    current_user: User = Depends(get_current_user),
):
    """
    Start Instagram OAuth for the authenticated user.
    """

    if not settings.instagram_app_id:
        raise HTTPException(
            status_code=500,
            detail="Instagram App ID is not configured",
        )

    state = create_oauth_state(
        user_id=current_user.id,
    )

    try:
        authorization_url = get_instagram_authorization_url(
            state=state,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=authorization_url,
        status_code=307,
    )


@router.get("/callback")
async def instagram_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete Instagram OAuth and persist the connected account.
    """

    if error:
        raise HTTPException(
            status_code=400,
            detail=error_description or error,
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing",
        )

    if not state:
        raise HTTPException(
            status_code=400,
            detail="OAuth state is missing",
        )

    try:
        user_id = verify_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state",
        ) from exc

    try:
        # Exchange the authorization code for a short-lived token.
        token_response = await exchange_code_for_access_token(
            code=code,
        )

        short_lived_token = token_response.get(
            "access_token",
        )

        if not short_lived_token:
            raise ValueError(
                "Instagram did not return an access token."
            )

        # Exchange the short-lived token for a long-lived token.
        long_lived_response = await get_long_lived_access_token(
            access_token=short_lived_token,
        )

        access_token = long_lived_response.get(
            "access_token",
        )

        if not access_token:
            raise ValueError(
                "Instagram did not return a long-lived access token."
            )

        expires_in = long_lived_response.get(
            "expires_in",
        )

        token_expires_at = None

        if expires_in is not None:
            token_expires_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    seconds=int(expires_in),
                )
            )

        # Identify the Instagram account using the newly obtained token.
        client = InstagramClient(
            access_token=access_token,
        )

        instagram_account = await client.get_account()

        instagram_account_id = instagram_account.get(
            "id",
        )
        instagram_username = instagram_account.get(
            "username",
        )

        if not instagram_account_id:
            raise ValueError(
                "Instagram did not return an account ID."
            )

        if not instagram_username:
            instagram_username = str(
                instagram_account_id,
            )

        # Make the OAuth connection idempotent.
        existing_account = (
            await SocialAccountService
            .get_account_by_platform_and_account_id(
                db=db,
                user_id=user_id,
                platform="instagram",
                account_id=str(instagram_account_id),
            )
        )

        if existing_account:
            account_data = SocialAccountUpdate(
                account_name=instagram_username,
                access_token=access_token,
                token_expires_at=token_expires_at,
                is_active=True,
            )

            saved_account = (
                await SocialAccountService.update_account(
                    db=db,
                    account=existing_account,
                    account_data=account_data,
                )
            )

        else:
            account_data = SocialAccountCreate(
                platform="instagram",
                account_name=instagram_username,
                account_id=str(instagram_account_id),
                access_token=access_token,
                token_expires_at=token_expires_at,
                is_active=True,
            )

            saved_account = (
                await SocialAccountService.create_account(
                    db=db,
                    user_id=user_id,
                    account_data=account_data,
                )
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Instagram connection failed: {exc}",
        ) from exc

    return {
        "status": "connected",
        "platform": saved_account.platform,
        "account_id": saved_account.account_id,
        "account_name": saved_account.account_name,
        "message": "Instagram account connected successfully.",
    }