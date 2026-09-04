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
SCHEDULED_POST_PROCESSING_QUEUE = (
    "socialpilot:scheduled_posts:processing"
)
SCHEDULED_POST_DELAYED_QUEUE = (
    "socialpilot:scheduled_posts:delayed"
)


class RedisQueue:
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        queue_name: str = SCHEDULED_POST_QUEUE,
        processing_queue_name: str = SCHEDULED_POST_PROCESSING_QUEUE,
        delayed_queue_name: str = SCHEDULED_POST_DELAYED_QUEUE,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.processing_queue_name = processing_queue_name
        self.delayed_queue_name = delayed_queue_name

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
        attempts: int = 0,
        next_retry_at: str | None = None,
    ) -> None:
        job = {
            "post_id": post_id,
            "user_id": user_id,
            "claimed_at": None,
            "attempts": attempts,
            "next_retry_at": next_retry_at,
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

        job.setdefault("attempts", 0)
        job.setdefault("next_retry_at", None)

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
                job = json.loads(raw_job)
            except json.JSONDecodeError:
                continue

            job.setdefault("attempts", 0)
            job.setdefault("next_retry_at", None)

            jobs.append(job)

        return jobs

    async def requeue_scheduled_post(
        self,
        post_id: int,
        user_id: int,
        attempts: int,
        next_retry_at: datetime | None,
    ) -> bool:
        """
        Move a failed scheduled-post job from the processing queue
        into the delayed retry queue.

        The delayed queue is a Redis sorted set. The retry timestamp
        is stored as the sorted-set score.
        """

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
                job.get("post_id") != post_id
                or job.get("user_id") != user_id
            ):
                continue

            retry_job = {
                "post_id": post_id,
                "user_id": user_id,
                "claimed_at": None,
                "attempts": attempts,
                "next_retry_at": (
                    next_retry_at.isoformat()
                    if next_retry_at is not None
                    else None
                ),
            }

            retry_job_json = json.dumps(retry_job)

            if next_retry_at is None:
                score = datetime.now(timezone.utc).timestamp()
            else:
                score = next_retry_at.timestamp()

            async with self.client.pipeline(
                transaction=True,
            ) as pipe:
                pipe.lrem(
                    self.processing_queue_name,
                    1,
                    raw_job,
                )
                pipe.zadd(
                    self.delayed_queue_name,
                    {
                        retry_job_json: score,
                    },
                )

                results = await pipe.execute()

            removed = results[0]

            if removed == 0:
                return False

            return True

        return False

    async def promote_due_retries(
        self,
        limit: int = 100,
    ) -> int:
        """
        Move delayed retry jobs whose retry time has arrived
        into the main scheduled-post queue.

        Returns the number of promoted jobs.
        """

        now_timestamp = datetime.now(timezone.utc).timestamp()

        due_jobs = await self.client.zrangebyscore(
            self.delayed_queue_name,
            min="-inf",
            max=now_timestamp,
            start=0,
            num=limit,
        )

        promoted = 0

        for raw_job in due_jobs:
            try:
                job = json.loads(raw_job)
            except json.JSONDecodeError:
                await self.client.zrem(
                    self.delayed_queue_name,
                    raw_job,
                )
                continue

            job["claimed_at"] = None

            ready_job = json.dumps(job)

            async with self.client.pipeline(
                transaction=True,
            ) as pipe:
                pipe.zrem(
                    self.delayed_queue_name,
                    raw_job,
                )
                pipe.rpush(
                    self.queue_name,
                    ready_job,
                )

                results = await pipe.execute()

            removed = results[0]

            if removed == 0:
                continue

            promoted += 1

        return promoted

    async def get_delayed_jobs(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all jobs currently waiting in the delayed retry queue.
        """

        raw_jobs = await self.client.zrange(
            self.delayed_queue_name,
            0,
            -1,
        )

        jobs = []

        for raw_job in raw_jobs:
            try:
                job = json.loads(raw_job)
            except json.JSONDecodeError:
                continue

            job.setdefault("attempts", 0)
            job.setdefault("next_retry_at", None)

            jobs.append(job)

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

            recovered_job = {
                "post_id": post_id,
                "user_id": user_id,
                "claimed_at": None,
                "attempts": job.get("attempts", 0),
                "next_retry_at": job.get("next_retry_at"),
            }

            async with self.client.pipeline(
                transaction=True,
            ) as pipe:
                pipe.lrem(
                    self.processing_queue_name,
                    1,
                    raw_job,
                )
                pipe.rpush(
                    self.queue_name,
                    json.dumps(recovered_job),
                )

                results = await pipe.execute()

            removed = results[0]

            if removed == 0:
                return False

            return True

        return False

    async def close(self) -> None:
        await self.client.aclose()


redis_queue = RedisQueue()