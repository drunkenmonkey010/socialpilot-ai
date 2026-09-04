import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.services.post import PostService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def process_job(job: dict) -> None:
    post_id = job.get("post_id")
    user_id = job.get("user_id")

    if not isinstance(post_id, int) or not isinstance(user_id, int):
        logger.error("Invalid Redis job: %s", job)
        return

    async with AsyncSessionLocal() as db:
        post = await PostService.get_post(
            db,
            post_id,
            user_id,
        )

        if post is None:
            logger.error(
                "Post not found for Redis job: post_id=%s user_id=%s",
                post_id,
                user_id,
            )
            return

        logger.info(
            "Processing Redis publishing job: "
            "post_id=%s user_id=%s platform=%s status=%s",
            post.id,
            user_id,
            post.platform,
            post.status,
        )

        if post.status != "publishing":
            logger.warning(
                "Skipping Redis job because post is not in publishing state: "
                "post_id=%s status=%s",
                post.id,
                post.status,
            )
            return

        await PostService.publish_scheduled_post(
            db,
            post,
            user_id,
        )


async def worker() -> None:
    logger.info("SocialPilot Redis publishing worker started.")

    try:
        while True:
            job = await redis_queue.dequeue_scheduled_post(
                timeout=5,
            )

            if job is None:
                continue

            logger.info("Received Redis job: %s", job)

            try:
                await process_job(job)

            except Exception:
                logger.exception(
                    "Redis job failed and remains in processing queue: %s",
                    job,
                )
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