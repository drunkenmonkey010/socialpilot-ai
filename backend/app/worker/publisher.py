import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.models.post import PostStatus
from app.services.post import PostService, ScheduledPublishError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


MAX_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 30


def calculate_backoff(attempt: int) -> int:
    """
    Calculate exponential retry backoff.

    Attempt 1 -> 30 seconds
    Attempt 2 -> 60 seconds
    Attempt 3 -> 120 seconds
    Attempt 4 -> 240 seconds
    """

    return INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))


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

    post_id = job.get("post_id")
    user_id = job.get("user_id")
    attempts = job.get("attempts", 0)

    if not isinstance(post_id, int) or not isinstance(user_id, int):
        logger.error("Invalid Redis job: %s", job)
        return True

    if not isinstance(attempts, int):
        attempts = 0

    attempts += 1

    logger.info(
        "Publishing attempt %s/%s: post_id=%s user_id=%s",
        attempts,
        MAX_ATTEMPTS,
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
                "post_id=%s user_id=%s",
                post_id,
                user_id,
            )
            return True

        logger.info(
            "Processing scheduled publishing job: "
            "post_id=%s user_id=%s platform=%s status=%s",
            post.id,
            user_id,
            post.platform,
            post.status,
        )

        if post.status == PostStatus.PUBLISHED.value:
            logger.info(
                "Post is already published. "
                "Acknowledging Redis job: post_id=%s",
                post.id,
            )
            return True

        if post.status != PostStatus.PUBLISHING.value:
            logger.warning(
                "Skipping Redis job because post is not in publishing state: "
                "post_id=%s status=%s",
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
                "Scheduled post published successfully: post_id=%s",
                post.id,
            )

            return True

        except ScheduledPublishError as exc:
            if not exc.retryable:
                logger.error(
                    "Permanent scheduled publishing failure: "
                    "post_id=%s error=%s",
                    post.id,
                    exc,
                )

                return True

            if attempts >= MAX_ATTEMPTS:
                logger.error(
                    "Maximum retry attempts reached: "
                    "post_id=%s attempts=%s",
                    post.id,
                    attempts,
                )

                post.status = PostStatus.FAILED.value

                await db.commit()

                return True

            backoff_seconds = calculate_backoff(
                attempts,
            )

            retry_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=backoff_seconds)
            )

            logger.warning(
                "Retryable publishing failure: "
                "post_id=%s attempt=%s/%s retry_in=%ss retry_at=%s error=%s",
                post.id,
                attempts,
                MAX_ATTEMPTS,
                backoff_seconds,
                retry_at.isoformat(),
                exc,
            )

            requeued = await redis_queue.requeue_scheduled_post(
                post_id=post_id,
                user_id=user_id,
                attempts=attempts,
                next_retry_at=retry_at,
            )

            if not requeued:
                logger.error(
                    "Failed to requeue retryable publishing job: "
                    "post_id=%s",
                    post_id,
                )
                return False

            return False


async def worker() -> None:
    logger.info("SocialPilot Redis publishing worker started.")

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

            acknowledged = await redis_queue.acknowledge_scheduled_post(
                post_id=job["post_id"],
                user_id=job["user_id"],
            )

            if acknowledged:
                logger.info(
                    "Redis job acknowledged successfully: "
                    "post_id=%s user_id=%s",
                    job["post_id"],
                    job["user_id"],
                )
            else:
                logger.warning(
                    "Redis job could not be acknowledged: %s",
                    job,
                )

    except asyncio.CancelledError:
        logger.info("Redis publishing worker cancelled.")
        raise

    finally:
        await redis_queue.close()
        logger.info("Redis publishing worker stopped.")


if __name__ == "__main__":
    asyncio.run(worker())