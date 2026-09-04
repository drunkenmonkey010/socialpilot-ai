import asyncio
import logging
from datetime import datetime, timezone

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.models.post import PostStatus
from app.services.post import PostService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

RECOVERY_INTERVAL_SECONDS = 30
STALE_AFTER_SECONDS = 300


async def recover_jobs() -> None:
    processing_jobs = await redis_queue.get_processing_jobs()

    if not processing_jobs:
        return

    logger.info(
        "Checking %s Redis processing job(s) for recovery.",
        len(processing_jobs),
    )

    for job in processing_jobs:
        post_id = job.get("post_id")
        user_id = job.get("user_id")
        claimed_at = job.get("claimed_at")

        if not isinstance(post_id, int) or not isinstance(user_id, int):
            logger.error(
                "Invalid processing job found during recovery: %s",
                job,
            )
            continue

        if not claimed_at:
            continue

        try:
            claimed_time = datetime.fromisoformat(claimed_at)

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
                    "post_id=%s user_id=%s",
                    post_id,
                    user_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    post_id,
                    user_id,
                )
                continue

            if post.status == PostStatus.PUBLISHED.value:
                logger.info(
                    "Post is already published. Removing stale Redis job: "
                    "post_id=%s",
                    post_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    post_id,
                    user_id,
                )
                continue

            if post.status == PostStatus.FAILED.value:
                logger.info(
                    "Post is already failed. Removing stale Redis job: "
                    "post_id=%s",
                    post_id,
                )

                await redis_queue.acknowledge_scheduled_post(
                    post_id,
                    user_id,
                )
                continue

            if post.status != PostStatus.PUBLISHING.value:
                logger.warning(
                    "Removing stale Redis job because post is no longer "
                    "publishing: post_id=%s status=%s",
                    post_id,
                    post.status,
                )

                await redis_queue.acknowledge_scheduled_post(
                    post_id,
                    user_id,
                )
                continue

        recovered = await redis_queue.recover_scheduled_post(
            post_id=post_id,
            user_id=user_id,
            stale_after_seconds=STALE_AFTER_SECONDS,
        )

        if recovered:
            logger.warning(
                "Recovered stale Redis job: post_id=%s user_id=%s",
                post_id,
                user_id,
            )


async def worker() -> None:
    logger.info("SocialPilot Redis recovery worker started.")

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
        logger.info("Redis recovery worker cancelled.")
        raise

    finally:
        await redis_queue.close()
        logger.info("Redis recovery worker stopped.")


if __name__ == "__main__":
    asyncio.run(worker())