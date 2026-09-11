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
TEST_DLQ_QUEUE = (
    "socialpilot:test:scheduled_posts:dead_letter"
)


@pytest_asyncio.fixture
async def queue():
    queue = RedisQueue(
        queue_name=TEST_QUEUE,
        processing_queue_name=TEST_PROCESSING_QUEUE,
        delayed_queue_name=TEST_DELAYED_QUEUE,
        dlq_queue_name=TEST_DLQ_QUEUE,
    )

    await queue.client.delete(
        TEST_QUEUE,
        TEST_PROCESSING_QUEUE,
        TEST_DELAYED_QUEUE,
        TEST_DLQ_QUEUE,
    )

    yield queue

    await queue.client.delete(
        TEST_QUEUE,
        TEST_PROCESSING_QUEUE,
        TEST_DELAYED_QUEUE,
        TEST_DLQ_QUEUE,
    )

    await queue.close()


@pytest.mark.asyncio
async def test_enqueue_creates_unique_job_ids(queue):
    first_job_id = await queue.enqueue_scheduled_post(
        post_id=1,
        user_id=10,
    )

    second_job_id = await queue.enqueue_scheduled_post(
        post_id=1,
        user_id=10,
    )

    assert first_job_id
    assert second_job_id
    assert first_job_id != second_job_id


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
    assert job["post_id"] == 2
    assert job["user_id"] == 20

    processing_jobs = await queue.get_processing_jobs()

    assert len(processing_jobs) == 1
    assert processing_jobs[0]["job_id"] == job_id


@pytest.mark.asyncio
async def test_acknowledge_uses_job_id_and_does_not_ack_another_same_post_job(
    queue,
):
    first_job_id = await queue.enqueue_scheduled_post(
        post_id=3,
        user_id=30,
    )

    second_job_id = await queue.enqueue_scheduled_post(
        post_id=3,
        user_id=30,
    )

    dequeued_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert dequeued_job is not None

    dequeued_job_id = dequeued_job["job_id"]

    assert dequeued_job_id in {
        first_job_id,
        second_job_id,
    }

    remaining_job_id = (
        second_job_id
        if dequeued_job_id == first_job_id
        else first_job_id
    )

    acknowledged = await queue.acknowledge_scheduled_post(
        job_id=dequeued_job_id,
    )

    assert acknowledged is True

    processing_jobs = await queue.get_processing_jobs()

    assert len(processing_jobs) == 0

    pending_jobs = await queue.client.lrange(
        TEST_QUEUE,
        0,
        -1,
    )

    assert len(pending_jobs) == 1

    remaining_job = queue._parse_job(
        pending_jobs[0],
    )

    assert remaining_job is not None
    assert remaining_job["job_id"] == remaining_job_id


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

    delayed_jobs = await queue.get_delayed_jobs()

    assert len(delayed_jobs) == 1
    assert delayed_jobs[0]["job_id"] == job_id
    assert delayed_jobs[0]["attempts"] == 1


@pytest.mark.asyncio
async def test_delayed_retry_promotion_preserves_job_id(queue):
    job_id = await queue.enqueue_scheduled_post(
        post_id=5,
        user_id=50,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None

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

    promoted = await queue.promote_due_retries(
        limit=100,
    )

    assert promoted == 1

    promoted_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert promoted_job is not None
    assert promoted_job["job_id"] == job_id
    assert promoted_job["attempts"] == 2


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

    processing_job["claimed_at"] = (
        datetime.now(timezone.utc)
        - timedelta(minutes=10)
    ).isoformat()

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

    recovered_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert recovered_job is not None
    assert recovered_job["job_id"] == job_id


@pytest.mark.asyncio
async def test_move_to_dead_letter_preserves_job_id_and_failure_details(
    queue,
):
    job_id = await queue.enqueue_scheduled_post(
        post_id=7,
        user_id=70,
    )

    job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert job is not None
    assert job["job_id"] == job_id

    moved = await queue.move_to_dead_letter(
        job_id=job_id,
        failure_type="retry_exhausted",
        error="simulated terminal failure",
    )

    assert moved is True

    processing_jobs = await queue.get_processing_jobs()
    dlq_jobs = await queue.get_dead_letter_jobs()

    assert processing_jobs == []
    assert len(dlq_jobs) == 1

    dlq_job = dlq_jobs[0]

    assert dlq_job["job_id"] == job_id
    assert dlq_job["post_id"] == 7
    assert dlq_job["user_id"] == 70
    assert dlq_job["attempts"] == 0
    assert dlq_job["failure_type"] == "retry_exhausted"
    assert dlq_job["error"] == "simulated terminal failure"
    assert dlq_job["failed_at"] is not None


@pytest.mark.asyncio
async def test_dead_letter_acknowledgement_uses_job_id(
    queue,
):
    first_job_id = await queue.enqueue_scheduled_post(
        post_id=8,
        user_id=80,
    )

    second_job_id = await queue.enqueue_scheduled_post(
        post_id=8,
        user_id=80,
    )

    first_dequeued_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert first_dequeued_job is not None

    first_dequeued_job_id = first_dequeued_job["job_id"]

    assert first_dequeued_job_id in {
        first_job_id,
        second_job_id,
    }

    second_dequeued_job = await queue.dequeue_scheduled_post(
        timeout=1,
    )

    assert second_dequeued_job is not None

    second_dequeued_job_id = second_dequeued_job["job_id"]

    assert second_dequeued_job_id in {
        first_job_id,
        second_job_id,
    }

    assert (
        first_dequeued_job_id
        != second_dequeued_job_id
    )

    moved_first = await queue.move_to_dead_letter(
        job_id=first_dequeued_job_id,
        failure_type="permanent_failure",
        error="first failure",
    )

    assert moved_first is True

    moved_second = await queue.move_to_dead_letter(
        job_id=second_dequeued_job_id,
        failure_type="permanent_failure",
        error="second failure",
    )

    assert moved_second is True

    acknowledged = await queue.acknowledge_dead_letter_job(
        job_id=first_dequeued_job_id,
    )

    assert acknowledged is True

    dlq_jobs = await queue.get_dead_letter_jobs()

    assert len(dlq_jobs) == 1
    assert (
        dlq_jobs[0]["job_id"]
        == second_dequeued_job_id
    )


@pytest.mark.asyncio
async def test_move_to_dead_letter_fails_for_missing_processing_job(
    queue,
):
    moved = await queue.move_to_dead_letter(
        job_id="missing-job",
        failure_type="retry_exhausted",
        error="missing processing job",
    )

    assert moved is False

    assert await queue.get_dead_letter_jobs() == []