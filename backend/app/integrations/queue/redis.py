"""
Redis queue integration.

Redis is used as the job queue and coordination layer.
PostgreSQL remains the source of truth for post state.
"""

import json
import os
from typing import Any

import redis.asyncio as redis


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

SCHEDULED_POST_QUEUE = "socialpilot:scheduled_posts"


class RedisQueue:
    """Async Redis queue for SocialPilot background jobs."""

    def __init__(
        self,
        redis_url: str = REDIS_URL,
        queue_name: str = SCHEDULED_POST_QUEUE,
    ) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.client = redis.from_url(
            self.redis_url,
            decode_responses=True,
        )

    async def ping(self) -> bool:
        """Check whether Redis is reachable."""
        return bool(await self.client.ping())

    async def enqueue_scheduled_post(
        self,
        post_id: int,
        user_id: int,
    ) -> None:
        """Add a scheduled-post job to the Redis queue."""

        job = {
            "post_id": post_id,
            "user_id": user_id,
        }

        await self.client.rpush(
            self.queue_name,
            json.dumps(job),
        )

    async def dequeue_scheduled_post(
        self,
        timeout: int = 0,
    ) -> dict[str, Any] | None:
        """
        Remove and return the next scheduled-post job.

        timeout=0 means wait indefinitely for a job.
        """

        result = await self.client.blpop(
            self.queue_name,
            timeout=timeout,
        )

        if result is None:
            return None

        _, raw_job = result

        return json.loads(raw_job)

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.client.aclose()


redis_queue = RedisQueue()