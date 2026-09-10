from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.platforms.errors import PlatformTransientError
from app.integrations.platforms.registry import platform_registry
from app.integrations.platforms.setup import register_platforms
from app.integrations.platforms.types import ReconciliationResult
from app.models.post import Post, PostStatus
from app.models.publication import Publication, PublicationStatus
from app.models.social_account import SocialAccount
from app.repositories.post import PostRepository
from app.repositories.publication import PublicationRepository
from app.repositories.social_account import SocialAccountRepository


class PublicationService:
    """
    Generic publication orchestration service.

    This service coordinates:

        Post
            ↓
        SocialAccount
            ↓
        Publication
            ↓
        PlatformRegistry
            ↓
        PlatformPublisher

    Platform-specific behavior remains inside platform adapters.

    The Publication table is the durable source of truth when a real
    SocialAccount record is available.

    Existing Post-level publication state remains supported so the
    current API, worker, recovery flow, and tests can transition
    safely to the durable Publication model.
    """

    @staticmethod
    def build_publication_key(
        post: Post,
    ) -> str:
        """
        Build the existing Post-level publication identity.

        This remains stable across retries, Redis requeues, worker
        restarts, and recovery operations.
        """

        platform = post.platform.lower().strip()

        return f"socialpilot:post:{post.id}:{platform}"

    @staticmethod
    def build_account_publication_key(
        post: Post,
        social_account: SocialAccount,
    ) -> str:
        """
        Build the durable account-specific publication identity.

        Including the social account ID allows the same Post to
        eventually be published to multiple accounts.
        """

        return (
            f"socialpilot:post:{post.id}:"
            f"account:{social_account.id}"
        )

    @staticmethod
    async def ensure_publication_key(
        db: AsyncSession,
        post: Post,
    ) -> str:
        """
        Ensure the existing Post-level publication key exists.

        Existing keys are always preserved.
        """

        if post.publication_key:
            return post.publication_key

        publication_key = (
            PublicationService.build_publication_key(
                post,
            )
        )

        post.publication_key = publication_key

        await PostRepository.update(
            db,
            post,
        )

        return publication_key

    @staticmethod
    def get_publisher(
        platform: str,
    ):
        """
        Resolve the registered publisher for a platform.

        Registration happens here because API and worker processes
        may initialize independently.
        """

        register_platforms()

        return platform_registry.get(
            platform,
        )

    @staticmethod
    def classify_platform_error(
        publisher,
        exc: Exception,
    ) -> bool:
        """
        Ask the platform adapter whether an exception is retryable.
        """

        return publisher.classify_error(
            exc,
        )

    @staticmethod
    async def get_social_account(
        db: AsyncSession,
        platform: str,
        user_id: int,
    ) -> SocialAccount:
        """
        Resolve the active social account for a user and platform.
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
    async def get_or_create_publication(
        db: AsyncSession,
        post: Post,
        social_account: SocialAccount,
    ) -> Publication | None:
        """
        Resolve the durable Publication for a Post -> SocialAccount
        operation.

        During the migration to durable publication state, lightweight
        fake/mock accounts that do not expose a database ID return None.
        This preserves the existing Post-level behavior used by older
        tests and compatibility paths.
        """

        social_account_id = getattr(
            social_account,
            "id",
            None,
        )

        if social_account_id is None:
            return None

        existing = (
            await PublicationRepository.get_by_post_and_account(
                db,
                post.id,
                social_account_id,
            )
        )

        if existing is not None:
            return existing

        platform = post.platform.lower().strip()

        publication = Publication(
            post_id=post.id,
            social_account_id=social_account_id,
            platform=platform,
            publication_key=(
                PublicationService.build_account_publication_key(
                    post,
                    social_account,
                )
            ),
            status=PublicationStatus.PENDING.value,
        )

        try:
            return await PublicationRepository.create(
                db,
                publication,
            )

        except Exception:
            await db.rollback()

            existing = (
                await PublicationRepository.get_by_post_and_account(
                    db,
                    post.id,
                    social_account_id,
                )
            )

            if existing is not None:
                return existing

            raise

    @staticmethod
    async def _sync_post_from_publication(
        db: AsyncSession,
        post: Post,
        publication: Publication,
    ) -> Post:
        """
        Synchronize legacy Post publication fields from durable
        Publication state.
        """

        changed = False

        if publication.external_post_id:
            if post.external_post_id != publication.external_post_id:
                post.external_post_id = publication.external_post_id
                changed = True

            if post.status != PostStatus.PUBLISHED.value:
                post.status = PostStatus.PUBLISHED.value
                changed = True

            if post.published_at is None:
                post.published_at = (
                    publication.published_at
                    or datetime.now(timezone.utc)
                )
                changed = True

        if changed:
            await PostRepository.update(
                db,
                post,
            )

        return post

    @staticmethod
    async def reconcile(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> ReconciliationResult:
        """
        Determine whether a previous external publication already exists.

        The durable Publication record is used when a real social
        account is available. Otherwise the existing Post-level
        reconciliation behavior is preserved.
        """

        platform = post.platform.lower().strip()

        publisher = PublicationService.get_publisher(
            platform,
        )

        social_account = (
            await PublicationService.get_social_account(
                db,
                platform,
                user_id,
            )
        )

        publication = (
            await PublicationService.get_or_create_publication(
                db,
                post,
                social_account,
            )
        )

        # Compatibility path for lightweight fake accounts.
        if publication is None:
            publication_key = (
                await PublicationService.ensure_publication_key(
                    db,
                    post,
                )
            )

            reconciliation_result = await publisher.reconcile(
                account=social_account,
                content=post.content,
                publication_key=publication_key,
            )

            if (
                reconciliation_result.found
                and reconciliation_result.external_post_id
            ):
                published_post = (
                    await PostRepository.record_publication_result(
                        db,
                        post.id,
                        reconciliation_result.external_post_id,
                    )
                )

                if published_post is None:
                    raise RuntimeError(
                        f"Post {post.id} disappeared while recording "
                        "the reconciliation result."
                    )

            return reconciliation_result

        reconciliation_result = await publisher.reconcile(
            account=social_account,
            content=post.content,
            publication_key=publication.publication_key,
        )

        if (
            reconciliation_result.found
            and reconciliation_result.external_post_id
        ):
            updated_publication = (
                await PublicationRepository.mark_published(
                    db,
                    publication.id,
                    reconciliation_result.external_post_id,
                    reconciliation_result.metadata,
                )
            )

            if updated_publication is None:
                raise RuntimeError(
                    f"Publication {publication.id} disappeared while "
                    "recording the reconciliation result."
                )

            await PublicationService._sync_post_from_publication(
                db,
                post,
                updated_publication,
            )

        return reconciliation_result

    @staticmethod
    async def _reconcile_before_retry(
        db: AsyncSession,
        post: Post,
        user_id: int,
        publisher,
        publication: Publication | None,
    ) -> ReconciliationResult | None:
        """
        Reconcile a previous ambiguous publication before retrying.

        Reconciliation is only attempted when:

            1. The platform supports reconciliation.
            2. A previous attempt exists.
            3. No external post ID is already persisted.

        If reconciliation finds the external publication, publishing
        must not be attempted again.
        """

        capabilities = publisher.capabilities

        if not capabilities.reconciliation:
            return None

        # Use durable attempt state when available.
        if publication is not None:
            if publication.attempt_count <= 0:
                return None

            if publication.external_post_id:
                return None

        # Compatibility path uses the existing Post attempt counter.
        else:
            if post.publication_attempts <= 0:
                return None

            if post.external_post_id:
                return None

        try:
            result = await PublicationService.reconcile(
                db,
                post,
                user_id,
            )

        except Exception as exc:
            raise PlatformTransientError(
                "Publication reconciliation failed for "
                f"post {post.id}: {exc}"
            ) from exc

        if (
            result.found
            and result.external_post_id
        ):
            return result

        return None

    @staticmethod
    async def _publish_legacy(
        db: AsyncSession,
        post: Post,
        user_id: int,
        publisher,
        social_account: SocialAccount,
    ) -> Post:
        """
        Preserve the existing Post-level publication workflow.

        This path is used only when the supplied social account is a
        lightweight compatibility/mock object without a database ID.
        """

        if post.external_post_id:
            if post.status != PostStatus.PUBLISHED.value:
                post.status = PostStatus.PUBLISHED.value

                if post.published_at is None:
                    post.published_at = datetime.now(
                        timezone.utc,
                    )

                await PostRepository.update(
                    db,
                    post,
                )

            return post

        publication_key = (
            await PublicationService.ensure_publication_key(
                db,
                post,
            )
        )

        reconciled = await PublicationService._reconcile_before_retry(
            db,
            post,
            user_id,
            publisher,
            None,
        )

        if reconciled is not None:
            return post

        publisher.validate_content(
            post.content,
        )

        await PostRepository.increment_publication_attempts(
            db,
            post.id,
        )

        publication_result = await publisher.publish(
            account=social_account,
            content=post.content,
            publication_key=publication_key,
        )

        published_post = (
            await PostRepository.record_publication_result(
                db,
                post.id,
                publication_result.external_post_id,
            )
        )

        if published_post is None:
            raise RuntimeError(
                f"Post {post.id} disappeared while recording "
                "the publication result."
            )

        return published_post

    @staticmethod
    async def publish(
        db: AsyncSession,
        post: Post,
        user_id: int,
    ) -> Post:
        """
        Perform the generic publication workflow.

        Real database accounts use durable Publication state.

        Lightweight compatibility accounts use the existing Post-level
        publication state until all callers have migrated.
        """

        platform = post.platform.lower().strip()

        publisher = PublicationService.get_publisher(
            platform,
        )

        social_account = (
            await PublicationService.get_social_account(
                db,
                platform,
                user_id,
            )
        )

        publication = (
            await PublicationService.get_or_create_publication(
                db,
                post,
                social_account,
            )
        )

        # ------------------------------------------------------------------
        # Compatibility path.
        # ------------------------------------------------------------------

        if publication is None:
            return await PublicationService._publish_legacy(
                db,
                post,
                user_id,
                publisher,
                social_account,
            )

        # ------------------------------------------------------------------
        # Durable Publication path.
        # ------------------------------------------------------------------

        if (
            publication.status == PublicationStatus.PUBLISHED.value
            and publication.external_post_id
        ):
            return await PublicationService._sync_post_from_publication(
                db,
                post,
                publication,
            )

        if publication.external_post_id:
            await PublicationRepository.mark_published(
                db,
                publication.id,
                publication.external_post_id,
                publication.publication_metadata,
            )

            return await PublicationService._sync_post_from_publication(
                db,
                post,
                publication,
            )

        # Backward compatibility if the Post already contains an
        # external ID from before the Publication record existed.
        if post.external_post_id:
            await PublicationRepository.mark_published(
                db,
                publication.id,
                post.external_post_id,
                publication.publication_metadata,
            )

            return await PublicationService._sync_post_from_publication(
                db,
                post,
                publication,
            )

        reconciled = await PublicationService._reconcile_before_retry(
            db,
            post,
            user_id,
            publisher,
            publication,
        )

        if reconciled is not None:
            return post

        # Keep the existing Post-level key populated for compatibility
        # with Redis/recovery code.
        await PublicationService.ensure_publication_key(
            db,
            post,
        )

        publisher.validate_content(
            post.content,
        )

        publication = await PublicationRepository.increment_attempt(
            db,
            publication.id,
        )

        if publication is None:
            raise RuntimeError(
                "Publication disappeared while recording "
                "the publication attempt."
            )

        # Keep legacy attempt state synchronized.
        await PostRepository.increment_publication_attempts(
            db,
            post.id,
        )

        try:
            publication_result = await publisher.publish(
                account=social_account,
                content=post.content,
                publication_key=publication.publication_key,
            )

        except Exception as exc:
            retry_after_seconds = getattr(
                exc,
                "retry_after_seconds",
                None,
            )

            retryable = (
                PublicationService.classify_platform_error(
                    publisher,
                    exc,
                )
            )

            if retryable:
                await PublicationRepository.record_error(
                    db,
                    publication.id,
                    str(exc),
                    retry_after_seconds,
                )
            else:
                await PublicationRepository.mark_failed(
                    db,
                    publication.id,
                    str(exc),
                    retry_after_seconds,
                )

            raise

        publication = await PublicationRepository.mark_published(
            db,
            publication.id,
            publication_result.external_post_id,
            publication_result.metadata,
        )

        if publication is None:
            raise RuntimeError(
                "Publication disappeared while recording "
                "the publication result."
            )

        return await PublicationService._sync_post_from_publication(
            db,
            post,
            publication,
        )