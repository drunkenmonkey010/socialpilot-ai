import json
import os
import uuid
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
SCHEDULED_POST_DLQ = (
    "socialpilot:scheduled_posts:dead_letter"
)


class RedisQueue:
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        queue_name: str = SCHEDULED_POST_QUEUE,
        processing_queue_name: str = SCHEDULED_POST_PROCESSING_QUEUE,
        delayed_queue_name: str = SCHEDULED_POST_DELAYED_QUEUE,
        dlq_queue_name: str = SCHEDULED_POST_DLQ,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.processing_queue_name = processing_queue_name
        self.delayed_queue_name = delayed_queue_name
        self.dlq_queue_name = dlq_queue_name

        self.client = redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_timeout=None,
            socket_connect_timeout=5,
        )

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    @staticmethod
    def _create_job(
        post_id: int,
        user_id: int,
        attempts: int = 0,
        next_retry_at: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Redis publishing job.

        job_id is the unique identity of this queue job and remains
        unchanged as the job moves through pending, processing,
        delayed, and recovery states.
        """

        return {
            "job_id": job_id or str(uuid.uuid4()),
            "post_id": post_id,
            "user_id": user_id,
            "claimed_at": None,
            "attempts": attempts,
            "next_retry_at": next_retry_at,
        }

    @staticmethod
    def _parse_job(
        raw_job: str,
    ) -> dict[str, Any] | None:
        try:
            job = json.loads(raw_job)
        except json.JSONDecodeError:
            return None

        if not isinstance(job, dict):
            return None

        job.setdefault("job_id", None)
        job.setdefault("attempts", 0)
        job.setdefault("next_retry_at", None)
        job.setdefault("claimed_at", None)

        return job

    @staticmethod
    def _job_matches(
        raw_job: str,
        post_id: int,
        user_id: int,
    ) -> bool:
        job = RedisQueue._parse_job(raw_job)

        if job is None:
            return False

        return (
            job.get("post_id") == post_id
            and job.get("user_id") == user_id
        )

    @staticmethod
    def _job_id_matches(
        raw_job: str,
        job_id: str,
    ) -> bool:
        job = RedisQueue._parse_job(raw_job)

        if job is None:
            return False

        return job.get("job_id") == job_id

    async def has_scheduled_post_job(
        self,
        post_id: int,
        user_id: int,
    ) -> bool:
        """
        Check whether a scheduled publication job exists anywhere
        in the Redis lifecycle.

        A job may exist in:

            pending
                ↓
            processing
                ↓
            delayed retry
                ↓
            dead letter queue

        Recovery must not create another job if one already exists.
        """

        pending_jobs = await self.client.lrange(
            self.queue_name,
            0,
            -1,
        )

        for raw_job in pending_jobs:
            if self._job_matches(
                raw_job,
                post_id,
                user_id,
            ):
                return True

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        for raw_job in processing_jobs:
            if self._job_matches(
                raw_job,
                post_id,
                user_id,
            ):
                return True

        delayed_jobs = await self.client.zrange(
            self.delayed_queue_name,
            0,
            -1,
        )

        for raw_job in delayed_jobs:
            if self._job_matches(
                raw_job,
                post_id,
                user_id,
            ):
                return True

        dlq_jobs = await self.client.lrange(
            self.dlq_queue_name,
            0,
            -1,
        )

        for raw_job in dlq_jobs:
            if self._job_matches(
                raw_job,
                post_id,
                user_id,
            ):
                return True

        return False

    async def enqueue_scheduled_post(
        self,
        post_id: int,
        user_id: int,
        attempts: int = 0,
        next_retry_at: str | None = None,
        job_id: str | None = None,
    ) -> str:
        """
        Enqueue a scheduled publishing job.

        If job_id is supplied, the existing identity is preserved.
        Otherwise a new UUID is generated.
        """

        job = self._create_job(
            post_id=post_id,
            user_id=user_id,
            attempts=attempts,
            next_retry_at=next_retry_at,
            job_id=job_id,
        )

        await self.client.rpush(
            self.queue_name,
            json.dumps(job),
        )

        return job["job_id"]

    async def dequeue_scheduled_post(
        self,
        timeout: int = 5,
    ) -> dict[str, Any] | None:
        """
        Move one pending job into processing.

        The job_id remains unchanged.
        """

        raw_job = await self.client.brpoplpush(
            self.queue_name,
            self.processing_queue_name,
            timeout=timeout,
        )

        if raw_job is None:
            return None

        job = self._parse_job(raw_job)

        if job is None:
            await self.client.lrem(
                self.processing_queue_name,
                1,
                raw_job,
            )
            return None

        job["claimed_at"] = datetime.now(
            timezone.utc,
        ).isoformat()

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
        job_id: str,
    ) -> bool:
        """Acknowledge a specific processing job by job_id."""

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        for raw_job in processing_jobs:
            if not self._job_id_matches(
                raw_job,
                job_id,
            ):
                continue

            removed = await self.client.lrem(
                self.processing_queue_name,
                1,
                raw_job,
            )

            return removed > 0

        return False

    async def get_processing_jobs(
        self,
    ) -> list[dict[str, Any]]:
        raw_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        jobs = []

        for raw_job in raw_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            jobs.append(job)

        return jobs

    async def requeue_scheduled_post(
        self,
        job_id: str,
        attempts: int,
        next_retry_at: datetime | None,
    ) -> bool:
        """Move a failed processing job into the delayed retry queue."""

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        for raw_job in processing_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            if job.get("job_id") != job_id:
                continue

            retry_job = {
                "job_id": job_id,
                "post_id": job["post_id"],
                "user_id": job["user_id"],
                "claimed_at": None,
                "attempts": attempts,
                "next_retry_at": (
                    next_retry_at.isoformat()
                    if next_retry_at is not None
                    else None
                ),
            }

            retry_job_json = json.dumps(
                retry_job,
            )

            if next_retry_at is None:
                score = datetime.now(
                    timezone.utc,
                ).timestamp()
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

    async def move_to_dead_letter(
        self,
        job_id: str,
        failure_type: str,
        error: str,
    ) -> bool:
        """
        Move a specific processing job into the dead-letter queue.

        The original job_id is preserved.

        The move is performed conditionally by a Redis Lua script so
        the job is only added to the DLQ if it was actually removed
        from the processing queue.
        """

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        for raw_job in processing_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            if job.get("job_id") != job_id:
                continue

            job["failure_type"] = failure_type
            job["error"] = error
            job["failed_at"] = datetime.now(
                timezone.utc,
            ).isoformat()
            job["next_retry_at"] = None

            dlq_job = json.dumps(job)

            script = """
            local removed = redis.call(
                'LREM',
                KEYS[1],
                1,
                ARGV[1]
            )

            if removed == 0 then
                return 0
            end

            redis.call(
                'RPUSH',
                KEYS[2],
                ARGV[2]
            )

            return 1
            """

            result = await self.client.eval(
                script,
                2,
                self.processing_queue_name,
                self.dlq_queue_name,
                raw_job,
                dlq_job,
            )

            return bool(result)

        return False

    async def get_dead_letter_jobs(
        self,
    ) -> list[dict[str, Any]]:
        """Return all jobs currently in the dead-letter queue."""

        raw_jobs = await self.client.lrange(
            self.dlq_queue_name,
            0,
            -1,
        )

        jobs = []

        for raw_job in raw_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            jobs.append(job)

        return jobs

    async def acknowledge_dead_letter_job(
        self,
        job_id: str,
    ) -> bool:
        """Remove a specific job from the dead-letter queue."""

        dlq_jobs = await self.client.lrange(
            self.dlq_queue_name,
            0,
            -1,
        )

        for raw_job in dlq_jobs:
            if not self._job_id_matches(
                raw_job,
                job_id,
            ):
                continue

            removed = await self.client.lrem(
                self.dlq_queue_name,
                1,
                raw_job,
            )

            return removed > 0

        return False

    async def promote_due_retries(
        self,
        limit: int = 100,
    ) -> int:
        """Move due delayed retry jobs into the main queue."""

        now_timestamp = datetime.now(
            timezone.utc,
        ).timestamp()

        due_jobs = await self.client.zrangebyscore(
            self.delayed_queue_name,
            min="-inf",
            max=now_timestamp,
            start=0,
            num=limit,
        )

        promoted = 0

        for raw_job in due_jobs:
            job = self._parse_job(raw_job)

            if job is None:
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
        """Return all jobs currently waiting in delayed retry."""

        raw_jobs = await self.client.zrange(
            self.delayed_queue_name,
            0,
            -1,
        )

        jobs = []

        for raw_job in raw_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            jobs.append(job)

        return jobs

    async def recover_scheduled_post(
        self,
        job_id: str,
        stale_after_seconds: int = 300,
    ) -> bool:
        """Recover one specific stale processing job."""

        processing_jobs = await self.client.lrange(
            self.processing_queue_name,
            0,
            -1,
        )

        now = datetime.now(
            timezone.utc,
        )

        for raw_job in processing_jobs:
            job = self._parse_job(raw_job)

            if job is None:
                continue

            if job.get("job_id") != job_id:
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
                "job_id": job_id,
                "post_id": job["post_id"],
                "user_id": job["user_id"],
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