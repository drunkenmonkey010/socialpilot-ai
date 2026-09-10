import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.integrations.queue.redis import RedisQueue


TEST_QUEUE = "socialpilot:test:scheduled_posts"
TEST_PROCESSING_QUEUE = (
    "socialpilot:test:scheduled_posts:processing"
)
TEST_DELAYED_QUEUE = (
    "socialpilot:test:scheduled_posts:delayed"
)


@pytest_asyncio.fixture
async def queue():
    queue = RedisQueue(
        queue_name=TEST_QUEUE,
        processing_queue_name=TEST_PROCESSING_QUEUE,
        delayed_queue_name=TEST_DELAYED_QUEUE,
    )

    await queue.client.delete(
        TEST_QUEUE,
        TEST_PROCESSING_QUEUE,
        TEST_DELAYED_QUEUE,
    )

    yield queue

    await queue.client.delete(
        TEST_QUEUE,
        TEST_PROCESSING_QUEUE,
        TEST_DELAYED_QUEUE,
    )

    await queue.close()


@pytest.mark.asyncio
async def test_enqueue_creates_unique_job_id(queue):
    first_job_id = await queue.enqueue_scheduled_post(
        post_id=1,
        user_id=10,
    )

    second_job_id = await queue.enqueue_scheduled_post(
        post_id=2,
        user_id=20,
    )

    assert first_job_id != second_job_id

    jobs = await queue.client.lrange(
        TEST_QUEUE,
        0,
        -1,
    )

    assert len(jobs) == 2

    first_job = queue._parse_job(jobs[0])
    second_job = queue._parse_job(jobs[1])

    assert first_job is not None
    assert second_job is not None

    assert first_job["job_id"] == first_job_id
    assert second_job["job_id"] == second_job_id


@pytest.mark.asyncio
async def test_job_id_survives_pending_to_processing(queue):
    job_id = await queue.enqueue_scheduled_post(
        post_id=2,
        user_id=20,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None
    assert job["job_id"] == job_id

    processing_jobs = await queue.get_processing_jobs()

    assert len(processing_jobs) == 1
    assert processing_jobs[0]["job_id"] == job_id


@pytest.mark.asyncio
async def test_acknowledge_uses_job_id(queue):
    first_job_id = await queue.enqueue_scheduled_post(
        post_id=3,
        user_id=30,
    )

    second_job_id = await queue.enqueue_scheduled_post(
        post_id=3,
        user_id=30,
    )

    processing_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert processing_job is not None

    # Redis BRPOPLPUSH takes from the right side of the list,
    # therefore the second enqueued job is processed first.
    assert processing_job["job_id"] == second_job_id

    acknowledged = await queue.acknowledge_scheduled_post(
        job_id=second_job_id,
    )

    assert acknowledged is True

    processing_jobs = await queue.get_processing_jobs()

    assert processing_jobs == []

    # The first job is still pending and was not accidentally
    # acknowledged just because it belongs to the same post/user.
    pending_jobs = await queue.client.lrange(
        TEST_QUEUE,
        0,
        -1,
    )

    assert len(pending_jobs) == 1

    pending_job = queue._parse_job(
        pending_jobs[0],
    )

    assert pending_job is not None
    assert pending_job["job_id"] == first_job_id


@pytest.mark.asyncio
async def test_retry_preserves_job_id(queue):
    job_id = await queue.enqueue_scheduled_post(
        post_id=4,
        user_id=40,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None
    assert job["job_id"] == job_id

    retry_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=60)
    )

    requeued = await queue.requeue_scheduled_post(
        job_id=job_id,
        attempts=1,
        next_retry_at=retry_at,
    )

    assert requeued is True

    processing_jobs = await queue.get_processing_jobs()
    delayed_jobs = await queue.get_delayed_jobs()

    assert processing_jobs == []
    assert len(delayed_jobs) == 1

    assert delayed_jobs[0]["job_id"] == job_id
    assert delayed_jobs[0]["attempts"] == 1


@pytest.mark.asyncio
async def test_delayed_retry_preserves_job_id_when_promoted(queue):
    job_id = await queue.enqueue_scheduled_post(
        post_id=5,
        user_id=50,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None
    assert job["job_id"] == job_id

    retry_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    requeued = await queue.requeue_scheduled_post(
        job_id=job_id,
        attempts=2,
        next_retry_at=retry_at,
    )

    assert requeued is True

    promoted = await queue.promote_due_retries()

    assert promoted == 1

    pending_jobs = await queue.client.lrange(
        TEST_QUEUE,
        0,
        -1,
    )

    assert len(pending_jobs) == 1

    pending_job = queue._parse_job(
        pending_jobs[0],
    )

    assert pending_job is not None
    assert pending_job["job_id"] == job_id
    assert pending_job["attempts"] == 2


@pytest.mark.asyncio
async def test_stale_recovery_preserves_job_id(queue):
    job_id = await queue.enqueue_scheduled_post(
        post_id=6,
        user_id=60,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None
    assert job["job_id"] == job_id

    processing_jobs = await queue.get_processing_jobs()

    assert len(processing_jobs) == 1

    processing_job = processing_jobs[0]

    stale_time = (
        datetime.now(timezone.utc)
        - timedelta(minutes=10)
    ).isoformat()

    processing_job["claimed_at"] = stale_time

    await queue.client.delete(
        TEST_PROCESSING_QUEUE,
    )

    await queue.client.rpush(
        TEST_PROCESSING_QUEUE,
        json.dumps(processing_job),
    )

    recovered = await queue.recover_scheduled_post(
        job_id=job_id,
        stale_after_seconds=300,
    )

    assert recovered is True

    processing_jobs = await queue.get_processing_jobs()

    assert processing_jobs == []

    pending_jobs = await queue.client.lrange(
        TEST_QUEUE,
        0,
        -1,
    )

    assert len(pending_jobs) == 1

    recovered_job = queue._parse_job(
        pending_jobs[0],
    )

    assert recovered_job is not None
    assert recovered_job["job_id"] == job_id