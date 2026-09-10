import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.models.post import PostStatus
from app.services.post import PostService, ScheduledPublishError
from app.worker.retry import retry_policy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def mark_post_failed(
    post_id: int,
    user_id: int,
) -> None:
    """Mark a post as FAILED after retries are exhausted."""

    async with AsyncSessionLocal() as db:
        post = await PostService.get_post(
            db,
            post_id,
            user_id,
        )

        if post is None:
            logger.error(
                "Cannot mark missing post as failed: "
                "post_id=%s user_id=%s",
                post_id,
                user_id,
            )
            return

        if post.status == PostStatus.PUBLISHED.value:
            logger.info(
                "Post is already published. "
                "Not marking it failed: post_id=%s",
                post_id,
            )
            return

        if post.status == PostStatus.PUBLISHING.value:
            post.status = PostStatus.FAILED.value

            await db.commit()

            logger.error(
                "Post marked as FAILED after maximum retry attempts: "
                "post_id=%s user_id=%s",
                post_id,
                user_id,
            )


async def process_job(
    job: dict,
) -> bool:
    """
    Process one scheduled publishing job.

    Returns:
        True  -> job completed and should be acknowledged.
        False -> job was requeued or should remain in processing.
    """

    job_id = job.get("job_id")
    post_id = job.get("post_id")
    user_id = job.get("user_id")
    attempts = job.get("attempts", 0)

    if (
        not isinstance(job_id, str)
        or not job_id
        or not isinstance(post_id, int)
        or not isinstance(user_id, int)
    ):
        logger.error(
            "Invalid Redis job: %s",
            job,
        )
        return True

    if not isinstance(attempts, int):
        attempts = 0

    attempts += 1

    logger.info(
        "Publishing attempt %s/%s: "
        "job_id=%s post_id=%s user_id=%s",
        attempts,
        retry_policy.max_attempts,
        job_id,
        post_id,
        user_id,
    )

    async with AsyncSessionLocal() as db:
        post = await PostService.get_post(
            db,
            post_id,
            user_id,
        )

        if post is None:
            logger.error(
                "Post not found for Redis job: "
                "job_id=%s post_id=%s user_id=%s",
                job_id,
                post_id,
                user_id,
            )
            return True

        logger.info(
            "Processing scheduled publishing job: "
            "job_id=%s post_id=%s user_id=%s platform=%s status=%s",
            job_id,
            post.id,
            user_id,
            post.platform,
            post.status,
        )

        if post.status == PostStatus.PUBLISHED.value:
            logger.info(
                "Post is already published. "
                "Acknowledging Redis job: job_id=%s post_id=%s",
                job_id,
                post.id,
            )
            return True

        if post.status != PostStatus.PUBLISHING.value:
            logger.warning(
                "Skipping Redis job because post is not in publishing state: "
                "job_id=%s post_id=%s status=%s",
                job_id,
                post.id,
                post.status,
            )
            return True

        try:
            await PostService.publish_scheduled_post(
                db,
                post,
                user_id,
            )

            logger.info(
                "Scheduled post published successfully: "
                "job_id=%s post_id=%s",
                job_id,
                post.id,
            )

            return True

        except ScheduledPublishError as exc:
            if not exc.retryable:
                logger.error(
                    "Permanent scheduled publishing failure: "
                    "job_id=%s post_id=%s error=%s",
                    job_id,
                    post.id,
                    exc,
                )

                return True

            if attempts >= retry_policy.max_attempts:
                logger.error(
                    "Maximum retry attempts reached: "
                    "job_id=%s post_id=%s attempts=%s",
                    job_id,
                    post.id,
                    attempts,
                )

                post.status = PostStatus.FAILED.value

                await db.commit()

                return True

            if exc.retry_after_seconds is not None:
                backoff_seconds = min(
                    exc.retry_after_seconds,
                    retry_policy.max_backoff_seconds,
                )

                logger.warning(
                    "Rate-limited publication. "
                    "Using platform Retry-After: "
                    "job_id=%s post_id=%s attempt=%s/%s "
                    "retry_in=%ss",
                    job_id,
                    post.id,
                    attempts,
                    retry_policy.max_attempts,
                    backoff_seconds,
                )

            else:
                backoff_seconds = (
                    retry_policy.calculate_retry_delay(
                        attempts,
                    )
                )

                logger.warning(
                    "Retryable publishing failure: "
                    "job_id=%s post_id=%s attempt=%s/%s "
                    "retry_in=%ss error=%s",
                    job_id,
                    post.id,
                    attempts,
                    retry_policy.max_attempts,
                    backoff_seconds,
                    exc,
                )

            retry_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=backoff_seconds)
            )

            requeued = await redis_queue.requeue_scheduled_post(
                job_id=job_id,
                attempts=attempts,
                next_retry_at=retry_at,
            )

            if not requeued:
                logger.error(
                    "Failed to requeue retryable publishing job: "
                    "job_id=%s post_id=%s",
                    job_id,
                    post_id,
                )
                return False

            return False


async def worker() -> None:
    logger.info(
        "SocialPilot Redis publishing worker started."
    )

    try:
        while True:
            job = await redis_queue.dequeue_scheduled_post(
                timeout=5,
            )

            if job is None:
                continue

            logger.info(
                "Received Redis publishing job: %s",
                job,
            )

            try:
                completed = await process_job(
                    job,
                )

            except Exception:
                logger.exception(
                    "Unexpected Redis publishing worker error: %s",
                    job,
                )
                continue

            if not completed:
                continue

            job_id = job.get("job_id")

            if not isinstance(job_id, str) or not job_id:
                logger.error(
                    "Cannot acknowledge Redis job without job_id: %s",
                    job,
                )
                continue

            acknowledged = await redis_queue.acknowledge_scheduled_post(
                job_id=job_id,
            )

            if acknowledged:
                logger.info(
                    "Redis job acknowledged successfully: "
                    "job_id=%s post_id=%s user_id=%s",
                    job_id,
                    job["post_id"],
                    job["user_id"],
                )
            else:
                logger.warning(
                    "Redis job could not be acknowledged: %s",
                    job,
                )

    except asyncio.CancelledError:
        logger.info(
            "Redis publishing worker cancelled."
        )
        raise

    finally:
        await redis_queue.close()

        logger.info(
            "Redis publishing worker stopped."
        )


if __name__ == "__main__":
    asyncio.run(worker())