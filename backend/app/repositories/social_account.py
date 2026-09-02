from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_account import SocialAccount


class SocialAccountRepository:
    """Database operations for SocialAccount entities."""

    @staticmethod
    async def create(
        db: AsyncSession,
        social_account: SocialAccount,
    ) -> SocialAccount:
        db.add(social_account)

        await db.commit()
        await db.refresh(social_account)

        return social_account

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        account_id: int,
    ) -> SocialAccount | None:
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_for_user(
        db: AsyncSession,
        account_id: int,
        user_id: int,
    ) -> SocialAccount | None:
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.user_id == user_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_platform_and_account_id(
        db: AsyncSession,
        user_id: int,
        platform: str,
        account_id: str,
    ) -> SocialAccount | None:
        """
        Find a social account belonging to a specific user
        using its platform and platform-specific account ID.
        """

        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.account_id == account_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user_id(
        db: AsyncSession,
        user_id: int,
    ) -> list[SocialAccount]:
        result = await db.execute(
            select(SocialAccount)
            .where(
                SocialAccount.user_id == user_id
            )
            .order_by(
                SocialAccount.created_at.desc()
            )
        )

        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        social_account: SocialAccount,
    ) -> SocialAccount:
        await db.commit()
        await db.refresh(social_account)

        return social_account

    @staticmethod
    async def delete(
        db: AsyncSession,
        social_account: SocialAccount,
    ) -> None:
        await db.delete(social_account)
        await db.commit()