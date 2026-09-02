from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandUpdate


class BrandRepository:
    """Repository for Brand database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: BrandCreate) -> Brand:
        """Create a new brand."""

        brand = Brand(
            user_id=data.user_id,
            name=data.name,
            description=data.description,
            website_url=data.website_url,
        )

        self.session.add(brand)
        await self.session.flush()
        await self.session.refresh(brand)

        return brand

    async def get_by_id(self, brand_id: int) -> Brand | None:
        """Get a brand by its ID."""

        result = await self.session.execute(
            select(Brand).where(Brand.id == brand_id)
        )

        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> list[Brand]:
        """Get all brands belonging to a user."""

        result = await self.session.execute(
            select(Brand)
            .where(Brand.user_id == user_id)
            .order_by(Brand.id)
        )

        return list(result.scalars().all())

    async def update(
        self,
        brand: Brand,
        data: BrandUpdate,
    ) -> Brand:
        """Update an existing brand."""

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(brand, field, value)

        await self.session.flush()
        await self.session.refresh(brand)

        return brand

    async def delete(self, brand: Brand) -> None:
        """Delete an existing brand."""

        await self.session.delete(brand)
        await self.session.flush()