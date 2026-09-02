from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.brand import BrandRepository
from app.schemas.brand import BrandCreate, BrandUpdate


class BrandService:
    """Service layer for Brand business logic."""

    def __init__(self, session: AsyncSession):
        self.repository = BrandRepository(session)

    async def create_brand(
        self,
        user_id: int,
        data: BrandCreate,
    ):
        """Create a new brand for the authenticated user."""

        return await self.repository.create(user_id, data)

    async def get_brand(
        self,
        brand_id: int,
        user_id: int,
    ):
        """Get a brand owned by the authenticated user."""

        return await self.repository.get_by_id(
            brand_id,
            user_id,
        )

    async def get_user_brands(
        self,
        user_id: int,
    ):
        """Get all brands belonging to the authenticated user."""

        return await self.repository.get_by_user_id(user_id)

    async def update_brand(
        self,
        brand_id: int,
        user_id: int,
        data: BrandUpdate,
    ):
        """Update a brand owned by the authenticated user."""

        brand = await self.repository.get_by_id(
            brand_id,
            user_id,
        )

        if brand is None:
            return None

        return await self.repository.update(
            brand,
            data,
        )

    async def delete_brand(
        self,
        brand_id: int,
        user_id: int,
    ) -> bool:
        """Delete a brand owned by the authenticated user."""

        brand = await self.repository.get_by_id(
            brand_id,
            user_id,
        )

        if brand is None:
            return False

        await self.repository.delete(brand)

        return True