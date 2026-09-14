from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.models.social_account import SocialAccount


class DashboardRepository:
    """Read-only database operations for the dashboard overview."""

    @staticmethod
    async def get_post_counts(
        db: AsyncSession,
        user_id: int,
    ) -> dict[str, int]:
        """
        Return post counts for all posts owned by the user.

        Ownership is resolved through:

            Post -> Campaign -> Brand -> User
        """

        result = await db.execute(
            select(
                Post.status,
                func.count(Post.id),
            )
            .join(
                Campaign,
                Post.campaign_id == Campaign.id,
            )
            .join(
                Brand,
                Campaign.brand_id == Brand.id,
            )
            .where(
                Brand.user_id == user_id,
            )
            .group_by(
                Post.status,
            )
        )

        counts = {
            status: count
            for status, count in result.all()
        }

        return {
            "drafts": counts.get(
                PostStatus.DRAFT.value,
                0,
            ),
            "needs_review": counts.get(
                PostStatus.PENDING_REVIEW.value,
                0,
            ),
            "scheduled": counts.get(
                PostStatus.SCHEDULED.value,
                0,
            ),
            "published": counts.get(
                PostStatus.PUBLISHED.value,
                0,
            ),
        }

    @staticmethod
    async def get_brand_count(
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """Return the number of brands owned by the user."""

        result = await db.execute(
            select(
                func.count(Brand.id),
            ).where(
                Brand.user_id == user_id,
            )
        )

        return int(result.scalar_one())

    @staticmethod
    async def get_primary_brand_name(
        db: AsyncSession,
        user_id: int,
    ) -> str:
        """
        Return the user's first-created brand name.

        A user can have multiple brands. The dashboard currently
        uses the first brand as the primary workspace label.
        """

        result = await db.execute(
            select(Brand.name)
            .where(
                Brand.user_id == user_id,
            )
            .order_by(
                Brand.id,
            )
            .limit(1)
        )

        brand_name = result.scalar_one_or_none()

        return brand_name or "Workspace"

    @staticmethod
    async def get_upcoming_posts(
        db: AsyncSession,
        user_id: int,
        limit: int = 5,
    ) -> list[tuple[Post, str]]:
        """
        Return upcoming scheduled posts belonging to the user.

        The campaign name is returned alongside each post so the
        API does not require the frontend to make another request.
        """

        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(
                Post,
                Campaign.name,
            )
            .join(
                Campaign,
                Post.campaign_id == Campaign.id,
            )
            .join(
                Brand,
                Campaign.brand_id == Brand.id,
            )
            .where(
                Brand.user_id == user_id,
                Post.status == PostStatus.SCHEDULED.value,
                Post.scheduled_at.is_not(None),
                Post.scheduled_at >= now,
            )
            .order_by(
                Post.scheduled_at.asc(),
            )
            .limit(limit)
        )

        return list(result.all())

    @staticmethod
    async def get_review_posts(
        db: AsyncSession,
        user_id: int,
        limit: int = 5,
    ) -> list[tuple[Post, str]]:
        """
        Return posts waiting for human approval.

        Only posts owned by the authenticated user are returned.
        """

        result = await db.execute(
            select(
                Post,
                Campaign.name,
            )
            .join(
                Campaign,
                Post.campaign_id == Campaign.id,
            )
            .join(
                Brand,
                Campaign.brand_id == Brand.id,
            )
            .where(
                Brand.user_id == user_id,
                Post.status
                == PostStatus.PENDING_REVIEW.value,
            )
            .order_by(
                Post.created_at.desc(),
            )
            .limit(limit)
        )

        return list(result.all())

    @staticmethod
    async def get_connected_account_count(
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """Return the number of active connected social accounts."""

        result = await db.execute(
            select(
                func.count(SocialAccount.id),
            ).where(
                SocialAccount.user_id == user_id,
                SocialAccount.is_active.is_(True),
            )
        )

        return int(result.scalar_one())