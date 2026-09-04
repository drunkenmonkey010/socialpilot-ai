"""
Database-backed scheduler for SocialPilot AI.

The scheduler:
1. Finds scheduled posts whose time has arrived.
2. Atomically claims each post.
3. Pushes the claimed post to Redis.
4. Leaves actual publishing to the Redis publisher worker.

PostgreSQL remains the source of truth for post state.
"""

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue
from app.repositories.post import PostRepository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("socialpilot.scheduler")

POLL_INTERVAL_SECONDS = 5


async def process_scheduled_posts() -> None:
    """
    Find due scheduled posts, claim them, and enqueue them in Redis.
    """

    # Discover due posts using a short-lived database session.
    async with AsyncSessionLocal() as db:
        due_posts = await PostRepository.get_due_scheduled_posts(db)

    if not due_posts:
        return

    for post, user_id in due_posts:
        async with AsyncSessionLocal() as db:
            try:
                # Atomically transition:
                #
                # SCHEDULED -> PUBLISHING
                #
                # This prevents multiple scheduler instances from
                # claiming the same post.
                claimed_post = await PostRepository.claim_scheduled_post(
                    db,
                    post.id,
                )

                if claimed_post is None:
                    logger.info(
                        "Post already claimed or no longer scheduled: "
                        "post_id=%s",
                        post.id,
                    )
                    continue

                logger.info(
                    "Claimed scheduled post: "
                    "post_id=%s user_id=%s platform=%s scheduled_at=%s",
                    claimed_post.id,
                    user_id,
                    claimed_post.platform,
                    claimed_post.scheduled_at,
                )

                # Put the claimed publishing job into Redis.
                await redis_queue.enqueue_scheduled_post(
                    post_id=claimed_post.id,
                    user_id=user_id,
                )

                logger.info(
                    "Scheduled post queued in Redis: "
                    "post_id=%s user_id=%s",
                    claimed_post.id,
                    user_id,
                )

            except Exception:
                logger.exception(
                    "Failed to queue scheduled post: post_id=%s",
                    post.id,
                )


async def scheduler_loop() -> None:
    """Continuously scan PostgreSQL for due scheduled posts."""

    logger.info(
        "SocialPilot scheduler started. Poll interval: %s seconds.",
        POLL_INTERVAL_SECONDS,
    )

    while True:
        try:
            await process_scheduled_posts()

        except Exception:
            logger.exception(
                "Unexpected error while processing scheduled posts."
            )

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main() -> None:
    try:
        await scheduler_loop()
    finally:
        await redis_queue.close()


if __name__ == "__main__":
    asyncio.run(main())