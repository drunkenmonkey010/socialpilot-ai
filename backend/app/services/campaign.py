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
        user_id: int,
        campaign_data: CampaignCreate,
    ) -> Campaign | None:
        """Create a campaign only under a brand owned by the user."""

        owns_brand = await CampaignRepository.brand_belongs_to_user(
            db,
            campaign_data.brand_id,
            user_id,
        )

        if not owns_brand:
            return None

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
        user_id: int,
    ) -> Campaign | None:
        """Retrieve a campaign only if the user owns its brand."""

        return await CampaignRepository.get_by_id_for_user(
            db,
            campaign_id,
            user_id,
        )

    @staticmethod
    async def get_brand_campaigns(
        db: AsyncSession,
        brand_id: int,
        user_id: int,
    ) -> list[Campaign] | None:
        """Retrieve campaigns only from a brand owned by the user."""

        owns_brand = await CampaignRepository.brand_belongs_to_user(
            db,
            brand_id,
            user_id,
        )

        if not owns_brand:
            return None

        return await CampaignRepository.get_by_brand_id_for_user(
            db,
            brand_id,
            user_id,
        )

    @staticmethod
    async def update_campaign(
        db: AsyncSession,
        campaign: Campaign,
        campaign_data: CampaignUpdate,
    ) -> Campaign:
        """Apply requested changes to an existing owned campaign."""

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
        """Delete an existing owned campaign."""

        await CampaignRepository.delete(
            db,
            campaign,
        )