from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.mastodon.oauth import publish_mastodon_status
from app.models.post import Post, PostStatus
from app.models.social_account import SocialAccount
from app.repositories.post import PostRepository
from app.repositories.social_account import SocialAccountRepository
from app.schemas.post import PostCreate, PostUpdate


class PostService:
    """Business operations for Post entities."""

    EDITABLE_STATUSES = {
        PostStatus.DRAFT.value,
        PostStatus.REJECTED.value,
    }

    @staticmethod
    async def create_post(
        db: AsyncSession,
        user_id: int,
        post_data: PostCreate,
    ) -> Post | None:
        """Create a new post as a draft under a campaign owned by the user."""

        owns_campaign = await PostRepository.campaign_belongs_to_user(
            db,
            post_data.campaign_id,
            user_id,
        )

        if not owns_campaign:
            return None

        post = Post(
            campaign_id=post_data.campaign_id,
            content=post_data.content,
            platform=post_data.platform,
            status=PostStatus.DRAFT.value,
            scheduled_at=post_data.scheduled_at,
        )

        return await PostRepository.create(
            db,
            post,
        )

    @staticmethod
    async def get_post(
        db: AsyncSession,
        post_id: int,
        user_id: int,
    ) -> Post | None:
        """Retrieve a post only if the user owns its campaign."""

        return await PostRepository.get_by_id_for_user(
            db,
            post_id,
            user_id,
        )

    @staticmethod
    async def get_campaign_posts(
        db: AsyncSession,
        campaign_id: int,
        user_id: int,
    ) -> list[Post] | None:
        """Retrieve posts only from a campaign owned by the user."""

        return await PostRepository.get_by_campaign_id_for_user(
            db,
            campaign_id,
            user_id,
        )

    @staticmethod
    async def update_post(
        db: AsyncSession,
        post: Post,
        post_data: PostUpdate,
    ) -> Post:
        """
        Edit a post while it is in an editable state.

        Approved, scheduled, publishing, published, and failed posts
        cannot be modified through the normal edit operation.
        """

        if post.status not in PostService.EDITABLE_STATUSES:
            raise ValueError(
                f"Post cannot be edited while in status '{post.status}'."
            )

        update_data = post_data.model_dump(
            exclude_unset=True,
        )

        for field, value in update_data.items():
            setattr(post, field, value)

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def submit_for_review(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        """
        Submit a draft or rejected post for human review.
        """

        if post.status not in PostService.EDITABLE_STATUSES:
            raise ValueError(
                f"Post cannot be submitted for review "
                f"while in status '{post.status}'."
            )

        post.status = PostStatus.PENDING_REVIEW.value

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def approve_post(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        """
        Approve a post after human review.

        This is the human-in-the-loop approval boundary.
        """

        if post.status != PostStatus.PENDING_REVIEW.value:
            raise ValueError(
                "Only posts pending review can be approved. "
                f"Current status: '{post.status}'."
            )

        post.status = PostStatus.APPROVED.value

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def reject_post(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        """
        Reject a post during human review.

        Rejected posts can subsequently be edited and resubmitted.
        """

        if post.status != PostStatus.PENDING_REVIEW.value:
            raise ValueError(
                "Only posts pending review can be rejected. "
                f"Current status: '{post.status}'."
            )

        post.status = PostStatus.REJECTED.value

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def schedule_post(
        db: AsyncSession,
        post: Post,
    ) -> Post:
        """
        Schedule an approved post for future publication.
        """

        if post.status != PostStatus.APPROVED.value:
            raise ValueError(
                "Only approved posts can be scheduled. "
                f"Current status: '{post.status}'."
            )

        if post.scheduled_at is None:
            raise ValueError(
                "A scheduled publication time is required."
            )

        post.status = PostStatus.SCHEDULED.value

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def publish_post(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Publish an approved post to its configured social platform.

        Human approval is mandatory before this method can execute.

        Lifecycle:

            APPROVED
                ↓
            PUBLISHING
                ↓
            PUBLISHED / FAILED
        """

        if post.status != PostStatus.APPROVED.value:
            raise ValueError(
                "Only approved posts can be published. "
                f"Current status: '{post.status}'."
            )

        platform = post.platform.lower().strip()

        if platform != "mastodon":
            raise ValueError(
                f"Publishing is not supported for platform '{post.platform}'."
            )

        social_account = (
            await SocialAccountRepository.get_by_platform_for_user(
                db,
                platform,
                user_id,
            )
        )

        if social_account is None:
            raise ValueError(
                "No active Mastodon account is connected "
                "for the current user."
            )

        if not social_account.is_active:
            raise ValueError(
                "The connected Mastodon account is inactive."
            )

        post.status = PostStatus.PUBLISHING.value

        await PostRepository.update(
            db,
            post,
        )

        try:
            mastodon_response = await publish_mastodon_status(
                access_token=social_account.access_token,
                content=post.content,
            )

            if not mastodon_response.get("id"):
                raise RuntimeError(
                    "Mastodon returned a successful response "
                    "without a status ID."
                )

            post.status = PostStatus.PUBLISHED.value
            post.published_at = datetime.now(timezone.utc)

            return await PostRepository.update(
                db,
                post,
            )

        except Exception:
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise

    @staticmethod
    async def delete_post(
        db: AsyncSession,
        post: Post,
    ) -> None:
        """Delete an existing post."""

        await PostRepository.delete(
            db,
            post,
        )