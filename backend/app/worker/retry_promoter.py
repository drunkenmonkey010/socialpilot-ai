import asyncio
import logging

from app.integrations.queue.redis import redis_queue


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


RETRY_PROMOTION_INTERVAL_SECONDS = 5
MAX_PROMOTIONS_PER_CYCLE = 100


async def promote_retries() -> None:
    """
    Move retry jobs whose delay has expired from the delayed
    Redis sorted set into the main scheduled-post queue.
    """

    promoted = await redis_queue.promote_due_retries(
        limit=MAX_PROMOTIONS_PER_CYCLE,
    )

    if promoted:
        logger.info(
            "Promoted %s delayed retry job(s) "
            "into the scheduled publishing queue.",
            promoted,
        )


async def worker() -> None:
    logger.info(
        "SocialPilot Redis retry promoter worker started."
    )

    try:
        while True:
            try:
                await promote_retries()

            except Exception:
                logger.exception(
                    "Error while promoting delayed retry jobs."
                )

            await asyncio.sleep(
                RETRY_PROMOTION_INTERVAL_SECONDS,
            )

    except asyncio.CancelledError:
        logger.info(
            "Redis retry promoter worker cancelled."
        )
        raise

    finally:
        await redis_queue.close()

        logger.info(
            "Redis retry promoter worker stopped."
        )


if __name__ == "__main__":
    asyncio.run(worker())