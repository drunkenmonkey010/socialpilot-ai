import json
import os
from datetime import datetime, timezone
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
            "claimed_at": None,
        }

        await self.client.rpush(
            self.queue_name,
            json.dumps(job),
        )

    async def dequeue_scheduled_post(
        self,
        timeout: int = 5,
    ) -> dict[str, Any] | None:
        raw_job = await self.client.brpoplpush(
            self.queue_name,
            self.processing_queue_name,
            timeout=timeout,
        )

        if raw_job is None:
            return None

        job = json.loads(raw_job)

        job["claimed_at"] = datetime.now(timezone.utc).isoformat()

        updated_job = json.dumps(job)

        await self.client.lrem(
            self.processing_queue_name,
            1,
            raw_job,
        )

        await self.client.lpush(
            self.processing_queue_name,
            updated_job,
        )

        return job

    async def acknowledge_scheduled_post(
        self,
        post_id: int,
        user_id: int,
    ) -> bool:
        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        for raw_job in processing_jobs:
            try:
                job = json.loads(raw_job)
            except json.JSONDecodeError:
                continue

            if (
                job.get("post_id") == post_id
                and job.get("user_id") == user_id
            ):
                removed = await self.client.lrem(
                    self.processing_queue_name,
                    1,
                    raw_job,
                )
                return removed > 0

        return False

    async def get_processing_jobs(self) -> list[dict[str, Any]]:
        raw_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        jobs = []

        for raw_job in raw_jobs:
            try:
                jobs.append(json.loads(raw_job))
            except json.JSONDecodeError:
                continue

        return jobs

    async def recover_scheduled_post(
        self,
        post_id: int,
        user_id: int,
        stale_after_seconds: int = 300,
    ) -> bool:
        """
        Recover one specific stale scheduled-post job.

        The caller is responsible for checking the PostgreSQL state
        before calling this method.
        """

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        now = datetime.now(timezone.utc)

        for raw_job in processing_jobs:
            try:
                job = json.loads(raw_job)
            except json.JSONDecodeError:
                continue

            if (
                job.get("post_id") != post_id
                or job.get("user_id") != user_id
            ):
                continue

            claimed_at_raw = job.get("claimed_at")

            if not claimed_at_raw:
                return False

            try:
                claimed_at = datetime.fromisoformat(
                    claimed_at_raw,
                )

                if claimed_at.tzinfo is None:
                    claimed_at = claimed_at.replace(
                        tzinfo=timezone.utc,
                    )

            except ValueError:
                return False

            age_seconds = (
                now - claimed_at
            ).total_seconds()

            if age_seconds < stale_after_seconds:
                return False

            removed = await self.client.lrem(
                self.processing_queue_name,
                1,
                raw_job,
            )

            if removed == 0:
                return False

            recovered_job = {
                "post_id": post_id,
                "user_id": user_id,
                "claimed_at": None,
            }

            await self.client.rpush(
                self.queue_name,
                json.dumps(recovered_job),
            )

            return True

        return False

    async def close(self) -> None:
        await self.client.aclose()


redis_queue = RedisQueue()