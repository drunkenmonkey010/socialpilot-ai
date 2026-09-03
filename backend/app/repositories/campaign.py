"""
Repository layer for campaign database operations.

The repository is responsible only for persistence-related operations.
Business rules belong in the service layer.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.campaign import Campaign


class CampaignRepository:
    """Database operations for Campaign entities."""

    @staticmethod
    async def create(
        db: AsyncSession,
        campaign: Campaign,
    ) -> Campaign:
        """Persist a new campaign and return the refreshed entity."""

        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)

        return campaign

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        campaign_id: int,
    ) -> Campaign | None:
        """Return a campaign by its primary key."""

        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_for_user(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> Campaign | None:
        """Return a campaign only if its brand belongs to the user."""

        result = await db.execute(
            select(Campaign)
            .join(Brand, Campaign.brand_id == Brand.id)
            .where(
                Campaign.id == campaign_id,
                Brand.user_id == user_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_campaign_with_brand_for_user(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> tuple[Campaign, Brand] | None:
        """
        Return a campaign and its brand only if the brand belongs
        to the specified user.
        """

        result = await db.execute(
            select(Campaign, Brand)
            .join(Brand, Campaign.brand_id == Brand.id)
            .where(
                Campaign.id == campaign_id,
                Brand.user_id == user_id,
            )
        )

        row = result.one_or_none()

        if row is None:
            return None

        campaign, brand = row

        return campaign, brand

    @staticmethod
    async def get_by_brand_id(
        db: AsyncSession,
        brand_id: int,
    ) -> list[Campaign]:
        """Return all campaigns belonging to a brand."""

        result = await db.execute(
            select(Campaign)
            .where(Campaign.brand_id == brand_id)
            .order_by(Campaign.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def get_by_brand_id_for_user(
        db: AsyncSession,
        brand_id: int,
        user_id: int,
    ) -> list[Campaign]:
        """Return campaigns only if the brand belongs to the user."""

        result = await db.execute(
            select(Campaign)
            .join(Brand, Campaign.brand_id == Brand.id)
            .where(
                Campaign.brand_id == brand_id,
                Brand.user_id == user_id,
            )
            .order_by(Campaign.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def brand_belongs_to_user(
        db: AsyncSession,
        brand_id: int,
        user_id: int,
    ) -> bool:
        """Return whether a brand belongs to the specified user."""

        result = await db.execute(
            select(Brand.id).where(
                Brand.id == brand_id,
                Brand.user_id == user_id,
            )
        )

        return result.scalar_one_or_none() is not None

    @staticmethod
    async def update(
        db: AsyncSession,
        campaign: Campaign,
    ) -> Campaign:
        """Persist changes to an existing campaign."""

        await db.commit()
        await db.refresh(campaign)

        return campaign

    @staticmethod
    async def delete(
        db: AsyncSession,
        campaign: Campaign,
    ) -> None:
        """Delete a campaign from the database."""

        await db.delete(campaign)
        await db.commit()