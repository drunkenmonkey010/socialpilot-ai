import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.repositories.post import PostRepository
from app.services.post import PostService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("socialpilot.scheduler")

POLL_INTERVAL_SECONDS = 5


async def process_scheduled_posts() -> None:
    """
    Find scheduled posts whose publication time has arrived,
    atomically claim them, and publish them.
    """

    # First session: discover posts that are due.
    async with AsyncSessionLocal() as db:
        due_posts = await PostRepository.get_due_scheduled_posts(db)

    if not due_posts:
        return

    for post, user_id in due_posts:
        # Use a fresh session for each post so one failure does not
        # interfere with processing other scheduled posts.
        async with AsyncSessionLocal() as db:
            try:
                # Atomically change:
                #
                # SCHEDULED -> PUBLISHING
                #
                # If another worker already claimed this post,
                # this returns None and we skip it.
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

                # Publish the claimed post.
                published_post = await PostService.publish_scheduled_post(
                    db,
                    claimed_post,
                    user_id,
                )

                logger.info(
                    "Scheduled post published successfully: "
                    "post_id=%s platform=%s published_at=%s",
                    published_post.id,
                    published_post.platform,
                    published_post.published_at,
                )

            except Exception:
                logger.exception(
                    "Failed to publish scheduled post: post_id=%s",
                    post.id,
                )


async def scheduler_loop() -> None:
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
    await scheduler_loop()


if __name__ == "__main__":
    asyncio.run(main())