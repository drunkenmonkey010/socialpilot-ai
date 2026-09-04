import json
import os
from typing import Any

import redis.asyncio as redis


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

SCHEDULED_POST_QUEUE = "socialpilot:scheduled_posts"
SCHEDULED_POST_PROCESSING_QUEUE = "socialpilot:scheduled_posts:processing"


class RedisQueue:
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        queue_name: str = SCHEDULED_POST_QUEUE,
        processing_queue_name: str = SCHEDULED_POST_PROCESSING_QUEUE,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.processing_queue_name = processing_queue_name

        self.client = redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_timeout=None,
            socket_connect_timeout=5,
        )

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def enqueue_scheduled_post(
        self,
        post_id: int,
        user_id: int,
    ) -> None:
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
        timeout: int = 5,
    ) -> dict[str, Any] | None:
        """
        Move one job from the main queue to the processing queue.

        BRPOPLPUSH gives us a basic acknowledgement/recovery mechanism:
        the job remains in the processing queue while the worker handles it.
        """

        raw_job = await self.client.brpoplpush(
            self.queue_name,
            self.processing_queue_name,
            timeout=timeout,
        )

        if raw_job is None:
            return None

        return json.loads(raw_job)

    async def acknowledge_scheduled_post(
        self,
        post_id: int,
        user_id: int,
    ) -> bool:
        """
        Remove a successfully processed job from the processing queue.
        """

        job = {
            "post_id": post_id,
            "user_id": user_id,
        }

        removed = await self.client.lrem(
            self.processing_queue_name,
            1,
            json.dumps(job),
        )

        return removed > 0

    async def get_processing_jobs(self) -> list[dict[str, Any]]:
        """
        Return jobs currently being processed.

        These jobs can be inspected for recovery if a worker crashes.
        """

        raw_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        return [
            json.loads(raw_job)
            for raw_job in raw_jobs
        ]

    async def close(self) -> None:
        await self.client.aclose()


redis_queue = RedisQueue()