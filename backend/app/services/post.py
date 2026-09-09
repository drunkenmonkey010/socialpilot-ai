from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.platforms import (
    register_platforms,
    platform_registry,
)
from app.models.post import Post, PostStatus
from app.repositories.post import PostRepository
from app.repositories.social_account import SocialAccountRepository
from app.schemas.post import PostCreate, PostUpdate


class ScheduledPublishError(Exception):
    """
    Error raised when a scheduled publication fails.

    retryable=True means the Redis worker may retry the publication.
    retryable=False means the publication should permanently fail.
    """

    def __init__(
        self,
        message: str,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.retryable = retryable


class PostService:
    """Business operations for Post entities."""

    EDITABLE_STATUSES = {
        PostStatus.DRAFT.value,
        PostStatus.REJECTED.value,
    }

    @staticmethod
    def _build_publication_key(post: Post) -> str:
        """
        Build the durable publication key for a post.

        The key is stable across retries, Redis requeues, worker restarts,
        and recovery operations.
        """

        platform = post.platform.lower().strip()

        return f"socialpilot:post:{post.id}:{platform}"

    @staticmethod
    async def _ensure_publication_key(
        db: AsyncSession,
        post: Post,
    ) -> str:
        """
        Ensure the post has a durable publication key.

        Existing keys are preserved so retries always refer to the same
        publication identity.
        """

        if post.publication_key:
            return post.publication_key

        publication_key = PostService._build_publication_key(post)

        post.publication_key = publication_key

        await PostRepository.update(
            db,
            post,
        )

        return publication_key

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
    def _get_publisher(platform: str):
        """
        Resolve the generic platform publisher.

        Platform-specific implementations are hidden behind the registry.
        """

        register_platforms()

        return platform_registry.get(platform)

    @staticmethod
    def _classify_platform_error(
        publisher,
        exc: Exception,
    ) -> bool:
        """
        Determine whether a platform error is retryable.

        Platform-specific error interpretation belongs to the adapter.
        The service only consumes the generic retryable/permanent result.
        """

        return publisher.classify_error(exc)

    @staticmethod
    async def _get_social_account(
        db: AsyncSession,
        platform: str,
        user_id: int,
    ):
        """
        Retrieve the active social account for a platform.

        The service does not contain platform-specific account logic.
        """

        social_account = (
            await SocialAccountRepository.get_by_platform_for_user(
                db,
                platform,
                user_id,
            )
        )

        if social_account is None:
            raise ValueError(
                f"No active {platform} account is connected "
                "for the current user."
            )

        if not social_account.is_active:
            raise ValueError(
                f"The connected {platform} account is inactive."
            )

        return social_account

    @staticmethod
    async def _publish_post(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Perform the actual platform publishing operation.

        Platform-specific API behavior is delegated to the registered
        PlatformPublisher adapter.

        The caller is responsible for validating the workflow state.
        """

        platform = post.platform.lower().strip()

        publisher = PostService._get_publisher(platform)

        social_account = await PostService._get_social_account(
            db,
            platform,
            user_id,
        )

        # If the external platform ID is already stored, the publication
        # has already succeeded. Never send another external POST.
        if post.external_post_id:
            if post.status != PostStatus.PUBLISHED.value:
                post.status = PostStatus.PUBLISHED.value

                if post.published_at is None:
                    post.published_at = datetime.now(timezone.utc)

                await PostRepository.update(
                    db,
                    post,
                )

            return post

        # Establish the stable publication identity before the external call.
        publication_key = await PostService._ensure_publication_key(
            db,
            post,
        )

        # Count this actual attempt immediately before contacting the
        # external platform.
        await PostRepository.increment_publication_attempts(
            db,
            post.id,
        )

        publication_result = await publisher.publish(
            account=social_account,
            content=post.content,
            publication_key=publication_key,
        )

        published_post = await PostRepository.record_publication_result(
            db,
            post.id,
            publication_result.external_post_id,
        )

        if published_post is None:
            raise RuntimeError(
                f"Post {post.id} disappeared while recording "
                "the publication result."
            )

        return published_post

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

        The scheduler performs:

            SCHEDULED → PUBLISHING

        before calling this method.
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

        platform = post.platform.lower().strip()

        try:
            publisher = PostService._get_publisher(platform)

        except Exception as exc:
            post.status = PostStatus.FAILED.value

            await PostRepository.update(
                db,
                post,
            )

            raise ScheduledPublishError(
                str(exc),
                retryable=False,
            ) from exc

        try:
            social_account = await PostService._get_social_account(
                db,
                platform,
                user_id,
            )

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

        # A recovered or retried job may reach this method after a previous
        # successful publication. The durable external ID is authoritative.
        if post.external_post_id:
            if post.status != PostStatus.PUBLISHED.value:
                post.status = PostStatus.PUBLISHED.value

                if post.published_at is None:
                    post.published_at = datetime.now(timezone.utc)

                await PostRepository.update(
                    db,
                    post,
                )

            return post

        # Establish the stable publication identity before the external call.
        publication_key = await PostService._ensure_publication_key(
            db,
            post,
        )

        try:
            # Count the external publication attempt immediately before
            # contacting the platform.
            await PostRepository.increment_publication_attempts(
                db,
                post.id,
            )

            publication_result = await publisher.publish(
                account=social_account,
                content=post.content,
                publication_key=publication_key,
            )

            published_post = await PostRepository.record_publication_result(
                db,
                post.id,
                publication_result.external_post_id,
            )

            if published_post is None:
                raise RuntimeError(
                    f"Post {post.id} disappeared while recording "
                    "the publication result."
                )

            return published_post

        except Exception as exc:
            retryable = PostService._classify_platform_error(
                publisher,
                exc,
            )

            if not retryable:
                post.status = PostStatus.FAILED.value

                await PostRepository.update(
                    db,
                    post,
                )

            raise ScheduledPublishError(
                str(exc),
                retryable=retryable,
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