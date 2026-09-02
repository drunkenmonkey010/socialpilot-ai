import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.integrations.instagram.oauth import (
    get_instagram_authorization_url,
)
from app.models.user import User


router = APIRouter(
    prefix="/social-accounts/instagram",
    tags=["Instagram"],
)


@router.get("/connect")
async def connect_instagram(
    current_user: User = Depends(get_current_user),
):
    if not settings.instagram_app_id:
        raise HTTPException(
            status_code=500,
            detail="Instagram App ID is not configured",
        )

    state = secrets.token_urlsafe(32)

    authorization_url = get_instagram_authorization_url(
        state=state,
    )

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
):
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

    return {
        "status": "authorization_received",
        "message": "Instagram authorization code received.",
    }