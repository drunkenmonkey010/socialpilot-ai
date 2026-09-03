from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus


class PostRepository:
    """Database operations for Post entities."""

    @staticmethod
    async def create(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        db.add(post)
        await db.commit()
        await db.refresh(post)

        return post

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        post_id: int,
    ) -> Post | None:
        result = await db.execute(
            select(Post).where(
                Post.id == post_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_for_user(
        db: AsyncSession,
        post_id: int,
        user_id: int,
    ) -> Post | None:
        result = await db.execute(
            select(Post)
            .join(Post.campaign)
            .join(Campaign.brand)
            .where(
                Post.id == post_id,
                Campaign.brand.has(
                    user_id=user_id,
                ),
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_campaign_id(
        db: AsyncSession,
        campaign_id: int,
    ) -> list[Post]:
        result = await db.execute(
            select(Post)
            .where(
                Post.campaign_id == campaign_id,
            )
            .order_by(Post.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def get_by_campaign_id_for_user(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> list[Post]:
        result = await db.execute(
            select(Post)
            .join(Post.campaign)
            .join(Campaign.brand)
            .where(
                Post.campaign_id == campaign_id,
                Campaign.brand.has(
                    user_id=user_id,
                ),
            )
            .order_by(Post.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def campaign_belongs_to_user(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> bool:
        result = await db.execute(
            select(Campaign.id)
            .join(Campaign.brand)
            .where(
                Campaign.id == campaign_id,
                Campaign.brand.has(
                    user_id=user_id,
                ),
            )
        )

        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_due_scheduled_posts(
        db: AsyncSession,
    ) -> list[tuple[Post, int]]:
        """
        Return scheduled posts whose publication time has arrived.

        The returned tuple contains:

            (post, user_id)

        The user ID is derived through:

            Post -> Campaign -> Brand -> User
        """

        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Post, Brand.user_id)
            .join(Campaign, Post.campaign_id == Campaign.id)
            .join(Brand, Campaign.brand_id == Brand.id)
            .where(
                Post.status == PostStatus.SCHEDULED.value,
                Post.scheduled_at.is_not(None),
                Post.scheduled_at <= now,
            )
            .order_by(Post.scheduled_at.asc())
        )

        return list(result.all())

    @staticmethod
    async def claim_scheduled_post(
        db: AsyncSession,
        post_id: int,
    ) -> Post | None:
        """
        Atomically claim a scheduled post for publishing.

        Only a post currently in SCHEDULED state can be claimed.

        The status transition:

            SCHEDULED -> PUBLISHING

        happens inside a single database transaction.
        """

        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
                Post.status == PostStatus.SCHEDULED.value,
            )
            .values(
                status=PostStatus.PUBLISHING.value,
            )
            .returning(Post)
        )

        post = result.scalar_one_or_none()

        if post is None:
            await db.rollback()
            return None

        await db.commit()

        return post

    @staticmethod
    async def update(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        await db.commit()
        await db.refresh(post)

        return post

    @staticmethod
    async def delete(
        db: AsyncSession,
        post: Post,
    ) -> None:
        await db.delete(post)
        await db.commit()