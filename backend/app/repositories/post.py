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
    async def get_publishing_posts(
        db: AsyncSession,
    ) -> list[tuple[Post, int]]:
        """
        Return posts currently in PUBLISHING state.

        The returned tuple contains:

            (post, user_id)

        This is used by recovery to detect the failure window where
        PostgreSQL successfully transitioned a post to PUBLISHING but
        Redis enqueueing did not complete.
        """

        result = await db.execute(
            select(Post, Brand.user_id)
            .join(Campaign, Post.campaign_id == Campaign.id)
            .join(Brand, Campaign.brand_id == Brand.id)
            .where(
                Post.status == PostStatus.PUBLISHING.value,
            )
            .order_by(Post.id.asc())
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
    async def get_by_publication_key(
        db: AsyncSession,
        publication_key: str,
    ) -> Post | None:
        """
        Find a post using its durable publication idempotency key.

        The publication key is stable across retries and worker restarts.
        """

        result = await db.execute(
            select(Post).where(
                Post.publication_key == publication_key,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def increment_publication_attempts(
        db: AsyncSession,
        post_id: int,
    ) -> int:
        """
        Atomically increment the number of external publication attempts.

        Returns the new attempt count.
        """

        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
            )
            .values(
                publication_attempts=Post.publication_attempts + 1,
            )
            .returning(Post.publication_attempts)
        )

        attempts = result.scalar_one_or_none()

        if attempts is None:
            await db.rollback()
            raise ValueError(
                f"Post {post_id} was not found while "
                "incrementing publication attempts."
            )

        await db.commit()

        return attempts

    @staticmethod
    async def record_publication_result(
        db: AsyncSession,
        post_id: int,
        external_post_id: str,
    ) -> Post | None:
        """
        Persist the external platform publication ID and mark the post
        published.

        The external ID is the durable evidence that the platform
        accepted the publication.
        """

        result = await db.execute(
            update(Post)
            .where(
                Post.id == post_id,
            )
            .values(
                external_post_id=external_post_id,
                status=PostStatus.PUBLISHED.value,
                published_at=datetime.now(timezone.utc),
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