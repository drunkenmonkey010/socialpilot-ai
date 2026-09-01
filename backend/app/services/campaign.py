"""
Service layer for campaign business logic.

The service layer sits between API routes and repositories.
It coordinates validation, business rules, and persistence without
containing HTTP-specific logic.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.repositories.campaign import CampaignRepository
from app.schemas.campaign import CampaignCreate, CampaignUpdate


class CampaignService:
    """Business operations for Campaign entities."""

    @staticmethod
    async def create_campaign(
        db: AsyncSession,
        campaign_data: CampaignCreate,
    ) -> Campaign:
        """Create and persist a new campaign."""

        campaign = Campaign(
            brand_id=campaign_data.brand_id,
            name=campaign_data.name,
            description=campaign_data.description,
            status=campaign_data.status,
        )

        return await CampaignRepository.create(db, campaign)

    @staticmethod
    async def get_campaign(
        db: AsyncSession,
        campaign_id: int,
    ) -> Campaign | None:
        """Retrieve a campaign by ID."""

        return await CampaignRepository.get_by_id(
            db,
            campaign_id,
        )

    @staticmethod
    async def get_brand_campaigns(
        db: AsyncSession,
        brand_id: int,
    ) -> list[Campaign]:
        """Retrieve all campaigns belonging to a brand."""

        return await CampaignRepository.get_by_brand_id(
            db,
            brand_id,
        )

    @staticmethod
    async def update_campaign(
        db: AsyncSession,
        campaign: Campaign,
        campaign_data: CampaignUpdate,
    ) -> Campaign:
        """Apply requested changes to an existing campaign."""

        update_data = campaign_data.model_dump(
            exclude_unset=True,
        )

        for field, value in update_data.items():
            setattr(campaign, field, value)

        return await CampaignRepository.update(
            db,
            campaign,
        )

    @staticmethod
    async def delete_campaign(
        db: AsyncSession,
        campaign: Campaign,
    ) -> None:
        """Delete an existing campaign."""

        await CampaignRepository.delete(
            db,
            campaign,
        )