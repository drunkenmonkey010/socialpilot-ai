"""
Repository layer for campaign database operations.

The repository is responsible only for persistence-related operations.
Business rules belong in the service layer.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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