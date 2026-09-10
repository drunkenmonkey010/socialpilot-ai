from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, PostStatus
from app.repositories.post import PostRepository
from app.schemas.post import PostCreate, PostUpdate
from app.services.publication import PublicationService


class ScheduledPublishError(Exception):
    """
    Error raised when a scheduled publication fails.

    retryable=True means the Redis worker may retry the publication.
    retryable=False means the publication should permanently fail.

    retry_after_seconds contains a platform-provided rate-limit delay
    when one is available.
    """

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)

        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class PostService:
    """
    Business operations for Post entities.

    PostService owns the post lifecycle and Human-in-the-Loop boundary.

    Publication mechanics are delegated to PublicationService.
    """

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
        """Submit a draft or rejected post for human review."""

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
        """Approve a post after human review."""

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
        """Reject a post during human review."""

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
        scheduled_at: datetime,
    ) -> Post:
        """Schedule an approved post for future publication."""

        if post.status != PostStatus.APPROVED.value:
            raise ValueError(
                "Only approved posts can be scheduled. "
                f"Current status: '{post.status}'."
            )

        if scheduled_at <= datetime.now(timezone.utc):
            raise ValueError(
                "Scheduled publication time must be in the future."
            )

        post.scheduled_at = scheduled_at
        post.status = PostStatus.SCHEDULED.value

        return await PostRepository.update(
            db,
            post,
        )

    @staticmethod
    async def _publish_post(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Delegate the actual publication operation to PublicationService.

        PostService owns lifecycle.
        PublicationService owns publication orchestration.
        """

        return await PublicationService.publish(
            db,
            post,
            user_id,
        )

    @staticmethod
    async def publish_post(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Immediately publish an approved post.

        Human approval is mandatory.

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

        post.status = PostStatus.PUBLISHING.value

        await PostRepository.update(
            db,
            post,
        )

        try:
            return await PostService._publish_post(
                db,
                post,
                user_id,
            )

        except Exception:
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise

    @staticmethod
    async def publish_scheduled_post(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Publish a scheduled post that has already been claimed
        by the scheduler.

        Retryable platform failures leave the post in PUBLISHING
        so the Redis worker can retry it.

        Permanent failures transition to FAILED.

        Scheduler lifecycle:

            SCHEDULED
                ↓
            PUBLISHING
                ↓
            PublicationService
                ↓
            PUBLISHED / retry / FAILED
        """

        if post.status != PostStatus.PUBLISHING.value:
            raise ValueError(
                "Scheduled post must be claimed before publishing. "
                f"Current status: '{post.status}'."
            )

        if post.scheduled_at is None:
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise ValueError(
                "Scheduled post does not have a scheduled publication time."
            )

        if post.scheduled_at > datetime.now(timezone.utc):
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise ValueError(
                "Scheduled publication time has not been reached yet."
            )

        publisher = None

        try:
            publisher = PublicationService.get_publisher(
                post.platform,
            )

            await PublicationService.get_social_account(
                db,
                post.platform.lower().strip(),
                user_id,
            )

            return await PublicationService.publish(
                db,
                post,
                user_id,
            )

        except ScheduledPublishError:
            raise

        except ValueError as exc:
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise ScheduledPublishError(
                str(exc),
                retryable=False,
            ) from exc

        except Exception as exc:
            if publisher is None:
                post.status = PostStatus.FAILED.value

                await PostRepository.update(
                    db,
                    post,
                )

                raise ScheduledPublishError(
                    str(exc),
                    retryable=False,
                ) from exc

            retryable = (
                PublicationService.classify_platform_error(
                    publisher,
                    exc,
                )
            )

            if not retryable:
                post.status = PostStatus.FAILED.value

                await PostRepository.update(
                    db,
                    post,
                )

            retry_after_seconds = getattr(
                exc,
                "retry_after_seconds",
                None,
            )

            raise ScheduledPublishError(
                str(exc),
                retryable=retryable,
                retry_after_seconds=retry_after_seconds,
            ) from exc

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