"""
Campaign API routes.

HTTP-specific concerns live here. Business logic is delegated to
CampaignService, which in turn uses CampaignRepository for persistence.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
)
from app.services.campaign import CampaignService


router = APIRouter(
    prefix="/campaigns",
    tags=["Campaigns"],
)


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    """Create a campaign under a brand owned by the current user."""

    campaign = await CampaignService.create_campaign(
        db,
        current_user.id,
        campaign_data,
    )

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return campaign


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    """Return a campaign owned by the current user."""

    campaign = await CampaignService.get_campaign(
        db,
        campaign_id,
        current_user.id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return campaign


@router.get(
    "/brand/{brand_id}",
    response_model=list[CampaignResponse],
)
async def get_brand_campaigns(
    brand_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CampaignResponse]:
    """Return campaigns from a brand owned by the current user."""

    campaigns = await CampaignService.get_brand_campaigns(
        db,
        brand_id,
        current_user.id,
    )

    if campaigns is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return campaigns


@router.patch(
    "/{campaign_id}",
    response_model=CampaignResponse,
)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    """Update a campaign only if the current user owns its brand."""

    campaign = await CampaignService.get_campaign(
        db,
        campaign_id,
        current_user.id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return await CampaignService.update_campaign(
        db,
        campaign,
        campaign_data,
    )


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a campaign only if the current user owns its brand."""

    campaign = await CampaignService.get_campaign(
        db,
        campaign_id,
        current_user.id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    await CampaignService.delete_campaign(
        db,
        campaign,
    )