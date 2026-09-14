from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    DashboardReviewPost,
    DashboardStats,
    DashboardUpcomingPost,
    DashboardUser,
    DashboardWorkspace,
)


class DashboardService:
    """Business logic for the authenticated dashboard."""

    @staticmethod
    async def get_overview(
        db: AsyncSession,
        current_user: User,
    ) -> DashboardOverviewResponse:
        """Build the dashboard overview for the authenticated user."""

        user_id = current_user.id

        post_counts = await DashboardRepository.get_post_counts(
            db,
            user_id,
        )

        brand_count = await DashboardRepository.get_brand_count(
            db,
            user_id,
        )

        brand_name = (
            await DashboardRepository.get_primary_brand_name(
                db,
                user_id,
            )
        )

        upcoming_rows = (
            await DashboardRepository.get_upcoming_posts(
                db,
                user_id,
            )
        )

        review_rows = (
            await DashboardRepository.get_review_posts(
                db,
                user_id,
            )
        )

        connected_account_count = (
            await DashboardRepository.get_connected_account_count(
                db,
                user_id,
            )
        )

        upcoming = [
            DashboardUpcomingPost(
                id=post.id,
                content=post.content,
                platform=post.platform,
                scheduled_at=post.scheduled_at,
                campaign_name=campaign_name,
            )
            for post, campaign_name in upcoming_rows
            if post.scheduled_at is not None
        ]

        needs_review = [
            DashboardReviewPost(
                id=post.id,
                content=post.content,
                platform=post.platform,
                created_at=post.created_at,
                campaign_name=campaign_name,
            )
            for post, campaign_name in review_rows
        ]

        return DashboardOverviewResponse(
            user=DashboardUser.model_validate(
                current_user,
            ),
            workspace=DashboardWorkspace(
                name=brand_name,
                brand_count=brand_count,
            ),
            stats=DashboardStats(
                drafts=post_counts["drafts"],
                needs_review=post_counts["needs_review"],
                scheduled=post_counts["scheduled"],
                published=post_counts["published"],
            ),
            upcoming=upcoming,
            needs_review=needs_review,
            connected_accounts=connected_account_count,
        )