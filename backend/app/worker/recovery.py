import asyncio
import logging
from datetime import datetime, timezone

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.models.post import PostStatus
from app.repositories.post import PostRepository
from app.services.post import PostService
from app.services.publication import PublicationService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

RECOVERY_INTERVAL_SECONDS = 30
STALE_AFTER_SECONDS = 300


async def reconcile_publishing_post(
    post_id: int,
    user_id: int,
) -> bool | None:
    """
    Attempt to reconcile an ambiguous PUBLISHING post.

    Returns:

        True:
            External publication was found and persisted as PUBLISHED.

        False:
            Reconciliation completed successfully, but no external
            publication was found or reconciliation is unsupported.

        None:
            Reconciliation could not be completed because an error
            occurred.

    None is intentionally different from False.

    A reconciliation error means the external publication state is
    unknown. Recovery must not interpret that state as permission to
    create another publication attempt.
    """

    async with AsyncSessionLocal() as db:
        post = await PostService.get_post(
            db,
            post_id,
            user_id,
        )

        if post is None:
            return False

        if post.status == PostStatus.PUBLISHED.value:
            return True

        if post.status != PostStatus.PUBLISHING.value:
            return False

        try:
            result = await PublicationService.reconcile(
                db,
                post,
                user_id,
            )

        except Exception:
            logger.exception(
                "Publication reconciliation failed: "
                "post_id=%s user_id=%s platform=%s",
                post_id,
                user_id,
                post.platform,
            )

            # The external publication state is unknown.
            #
            # Do not allow recovery to interpret this as
            # "publication not found" and republish.
            return None

        if result.found and result.external_post_id:
            logger.warning(
                "Reconciliation found an existing external publication: "
                "post_id=%s user_id=%s external_post_id=%s",
                post_id,
                user_id,
                result.external_post_id,
            )

            return True

        return False


async def recover_stale_processing_jobs() -> None:
    """
    Recover Redis processing jobs whose worker lease has gone stale.

    PostgreSQL remains the source of truth for the post lifecycle.

    Reconciliation is attempted before allowing another publication
    attempt. If reconciliation fails, the job is left in processing
    rather than being requeued into another external publication attempt.
    """

    processing_jobs = await redis_queue.get_processing_jobs()

    if not processing_jobs:
        return

    logger.info(
        "Checking %s Redis processing job(s) for recovery.",
        len(processing_jobs),
    )

    for job in processing_jobs:
        job_id = job.get("job_id")
        post_id = job.get("post_id")
        user_id = job.get("user_id")
        claimed_at = job.get("claimed_at")

        if (
            not isinstance(job_id, str)
            or not job_id
            or not isinstance(post_id, int)
            or not isinstance(user_id, int)
        ):
            logger.error(
                "Invalid processing job found during recovery: %s",
                job,
            )
            continue

        if not claimed_at:
            continue

        try:
            claimed_time = datetime.fromisoformat(
                claimed_at,
            )

            if claimed_time.tzinfo is None:
                claimed_time = claimed_time.replace(
                    tzinfo=timezone.utc,
                )

        except ValueError:
            logger.error(
                "Invalid claimed_at timestamp for job: %s",
                job,
            )
            continue

        age_seconds = (
            datetime.now(timezone.utc) - claimed_time
        ).total_seconds()

        if age_seconds < STALE_AFTER_SECONDS:
            continue

        async with AsyncSessionLocal() as db:
            post = await PostService.get_post(
                db,
                post_id,
                user_id,
            )

            if post is None:
                logger.warning(
                    "Removing Redis job because post no longer exists: "
                    "job_id=%s post_id=%s user_id=%s",
                    job_id,
                    post_id,
                    user_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    job_id=job_id,
                )
                continue

            if post.status == PostStatus.PUBLISHED.value:
                logger.info(
                    "Post is already published. Removing stale Redis job: "
                    "job_id=%s post_id=%s",
                    job_id,
                    post_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    job_id=job_id,
                )
                continue

            if post.status == PostStatus.FAILED.value:
                logger.info(
                    "Post is already failed. Removing stale Redis job: "
                    "job_id=%s post_id=%s",
                    job_id,
                    post_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    job_id=job_id,
                )
                continue

            if post.status != PostStatus.PUBLISHING.value:
                logger.warning(
                    "Removing stale Redis job because post is no longer "
                    "publishing: job_id=%s post_id=%s status=%s",
                    job_id,
                    post_id,
                    post.status,
                )

                await redis_queue.acknowledge_scheduled_post(
                    job_id=job_id,
                )
                continue

        # The worker may have successfully published externally and
        # crashed before recording external_post_id.
        #
        # Reconcile before allowing another external publication attempt.
        reconciled = await reconcile_publishing_post(
            post_id,
            user_id,
        )

        if reconciled is None:
            logger.error(
                "Leaving stale Redis job untouched because publication "
                "reconciliation failed: job_id=%s post_id=%s user_id=%s",
                job_id,
                post_id,
                user_id,
            )
            continue

        if reconciled:
            await redis_queue.acknowledge_scheduled_post(
                job_id=job_id,
            )
            continue

        recovered = await redis_queue.recover_scheduled_post(
            job_id=job_id,
            stale_after_seconds=STALE_AFTER_SECONDS,
        )

        if recovered:
            logger.warning(
                "Recovered stale Redis job after reconciliation: "
                "job_id=%s post_id=%s user_id=%s",
                job_id,
                post_id,
                user_id,
            )


async def recover_missing_redis_jobs() -> None:
    """
    Recover PUBLISHING posts that have no corresponding Redis job.

    Before creating a new Redis job, reconciliation is attempted so
    a successful external publication whose response was lost does
    not automatically become a duplicate publication.

    If reconciliation fails, the post is left in PUBLISHING without
    creating a new Redis job. The next recovery cycle can retry
    reconciliation.
    """

    async with AsyncSessionLocal() as db:
        publishing_posts = await PostRepository.get_publishing_posts(
            db,
        )

    if not publishing_posts:
        return

    logger.info(
        "Checking %s PUBLISHING post(s) for missing Redis jobs.",
        len(publishing_posts),
    )

    for post, user_id in publishing_posts:
        try:
            has_job = await redis_queue.has_scheduled_post_job(
                post_id=post.id,
                user_id=user_id,
            )

            if has_job:
                continue

            # First determine whether the external publication already
            # exists before creating another publication attempt.
            reconciled = await reconcile_publishing_post(
                post.id,
                user_id,
            )

            if reconciled is None:
                logger.error(
                    "Not creating Redis recovery job because publication "
                    "reconciliation failed: post_id=%s user_id=%s",
                    post.id,
                    user_id,
                )
                continue

            if reconciled:
                continue

            job_id = await redis_queue.enqueue_scheduled_post(
                post_id=post.id,
                user_id=user_id,
                attempts=post.publication_attempts,
            )

            logger.warning(
                "Recovered PUBLISHING post with no Redis job: "
                "job_id=%s post_id=%s user_id=%s platform=%s",
                job_id,
                post.id,
                user_id,
                post.platform,
            )

        except Exception:
            logger.exception(
                "Failed to recover missing Redis job: "
                "post_id=%s user_id=%s",
                post.id,
                user_id,
            )


async def recover_jobs() -> None:
    """Run all Redis publishing recovery checks."""

    await recover_stale_processing_jobs()
    await recover_missing_redis_jobs()


async def worker() -> None:
    logger.info(
        "SocialPilot Redis recovery worker started.",
    )

    try:
        while True:
            try:
                await recover_jobs()

            except Exception:
                logger.exception(
                    "Error while running Redis job recovery.",
                )

            await asyncio.sleep(
                RECOVERY_INTERVAL_SECONDS,
            )

    except asyncio.CancelledError:
        logger.info(
            "Redis recovery worker cancelled.",
        )
        raise

    finally:
        await redis_queue.close()

        logger.info(
            "Redis recovery worker stopped.",
        )


if __name__ == "__main__":
    asyncio.run(worker())