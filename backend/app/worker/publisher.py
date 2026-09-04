"""
Redis publishing worker.

Consumes scheduled-post jobs from Redis and publishes them
through the existing PostService.

PostgreSQL remains the source of truth for post state.
"""

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.services.post import PostService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("socialpilot.publisher")


async def process_job(job: dict) -> None:
    """
    Process one scheduled-post job from Redis.
    """

    post_id = job.get("post_id")
    user_id = job.get("user_id")

    if post_id is None or user_id is None:
        logger.error(
            "Invalid Redis job: %s",
            job,
        )
        return

    async with AsyncSessionLocal() as db:
        try:
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
                    "Post is not in publishing state. "
                    "Skipping: post_id=%s status=%s",
                    post.id,
                    post.status,
                )
                return

            published_post = await PostService.publish_scheduled_post(
                db,
                post,
                user_id,
            )

            logger.info(
                "Redis job completed successfully: "
                "post_id=%s platform=%s published_at=%s",
                published_post.id,
                published_post.platform,
                published_post.published_at,
            )

        except Exception:
            logger.exception(
                "Failed to process Redis publishing job: "
                "post_id=%s user_id=%s",
                post_id,
                user_id,
            )


async def worker_loop() -> None:
    """
    Continuously consume scheduled-post jobs from Redis.
    """

    logger.info(
        "SocialPilot Redis publishing worker started."
    )

    while True:
        try:
            job = await redis_queue.dequeue_scheduled_post(
                timeout=5,
            )

            if job is None:
                continue

            logger.info(
                "Received Redis job: %s",
                job,
            )

            await process_job(job)

        except asyncio.CancelledError:
            logger.info(
                "Redis publishing worker cancelled."
            )
            raise

        except Exception:
            logger.exception(
                "Unexpected error in Redis publishing worker."
            )

            # Prevent a tight error loop if Redis temporarily fails.
            await asyncio.sleep(2)


async def main() -> None:
    try:
        await worker_loop()
    finally:
        await redis_queue.close()


if __name__ == "__main__":
    asyncio.run(main())