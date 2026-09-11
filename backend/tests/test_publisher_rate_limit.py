from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.post import PostStatus
from app.services.post import ScheduledPublishError
from app.worker.publisher import process_job
from app.worker.retry import retry_policy


def make_fake_post(post_id: int):
    return type(
        "FakePost",
        (),
        {
            "id": post_id,
            "platform": "mastodon",
            "status": PostStatus.PUBLISHING.value,
        },
    )()


def make_job(
    post_id: int,
    user_id: int,
    attempts: int = 0,
    job_id: str | None = None,
) -> dict:
    return {
        "job_id": job_id or f"socialpilot:test:{post_id}",
        "post_id": post_id,
        "user_id": user_id,
        "attempts": attempts,
    }


async def run_rate_limit_job(
    job: dict,
    retry_after_seconds: int,
):
    fake_post = make_fake_post(job["post_id"])

    rate_limit_error = ScheduledPublishError(
        "Mastodon rate limited the request.",
        retryable=True,
        retry_after_seconds=retry_after_seconds,
    )

    with (
        patch(
            "app.worker.publisher.AsyncSessionLocal",
        ) as session_local_mock,
        patch(
            "app.worker.publisher.PostService.get_post",
            new=AsyncMock(return_value=fake_post),
        ),
        patch(
            "app.worker.publisher.PostService.publish_scheduled_post",
            new=AsyncMock(side_effect=rate_limit_error),
        ),
        patch(
            "app.worker.publisher.redis_queue.requeue_scheduled_post",
            new=AsyncMock(return_value=True),
        ) as requeue_mock,
    ):
        fake_db = AsyncMock()

        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_db
        session_context.__aexit__.return_value = None

        session_local_mock.return_value = session_context

        before = datetime.now(timezone.utc)

        result = await process_job(job)

    return result, requeue_mock, before


@pytest.mark.asyncio
async def test_rate_limit_retry_after_is_used_for_requeue():
    job = make_job(
        post_id=123,
        user_id=456,
        attempts=0,
        job_id="socialpilot:post:123:mastodon",
    )

    result, requeue_mock, before = await run_rate_limit_job(
        job,
        retry_after_seconds=120,
    )

    assert result is False

    requeue_mock.assert_awaited_once()

    call_kwargs = requeue_mock.await_args.kwargs

    assert call_kwargs["job_id"] == (
        "socialpilot:post:123:mastodon"
    )

    assert call_kwargs["attempts"] == 1

    retry_at = call_kwargs["next_retry_at"]

    actual_delay = (
        retry_at - before
    ).total_seconds()

    assert 119 <= actual_delay <= 121


@pytest.mark.asyncio
async def test_rate_limit_retry_after_overrides_exponential_backoff():
    job = make_job(
        post_id=456,
        user_id=789,
        attempts=1,
        job_id="socialpilot:post:456:mastodon",
    )

    result, requeue_mock, before = await run_rate_limit_job(
        job,
        retry_after_seconds=120,
    )

    assert result is False

    call_kwargs = requeue_mock.await_args.kwargs

    retry_at = call_kwargs["next_retry_at"]

    actual_delay = (
        retry_at - before
    ).total_seconds()

    assert 119 <= actual_delay <= 121

    assert call_kwargs["attempts"] == 2


@pytest.mark.asyncio
async def test_rate_limit_retry_after_is_capped():
    job = make_job(
        post_id=789,
        user_id=101,
        attempts=0,
        job_id="socialpilot:post:789:mastodon",
    )

    result, requeue_mock, before = await run_rate_limit_job(
        job,
        retry_after_seconds=999999,
    )

    assert result is False

    call_kwargs = requeue_mock.await_args.kwargs

    retry_at = call_kwargs["next_retry_at"]

    actual_delay = (
        retry_at - before
    ).total_seconds()

    expected_max = retry_policy.max_backoff_seconds

    assert expected_max - 1 <= actual_delay <= expected_max + 1

    assert call_kwargs["attempts"] == 1


async def run_permanent_failure_job(
    job: dict,
):
    fake_post = make_fake_post(job["post_id"])

    permanent_error = ScheduledPublishError(
        "Permanent platform failure.",
        retryable=False,
    )

    with (
        patch(
            "app.worker.publisher.AsyncSessionLocal",
        ) as session_local_mock,
        patch(
            "app.worker.publisher.PostService.get_post",
            new=AsyncMock(return_value=fake_post),
        ),
        patch(
            "app.worker.publisher.PostService.publish_scheduled_post",
            new=AsyncMock(side_effect=permanent_error),
        ),
        patch(
            "app.worker.publisher.redis_queue.move_to_dead_letter",
            new=AsyncMock(return_value=True),
        ) as dlq_mock,
    ):
        fake_db = AsyncMock()

        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_db
        session_context.__aexit__.return_value = None

        session_local_mock.return_value = session_context

        result = await process_job(job)

    return (
        result,
        fake_post,
        fake_db,
        dlq_mock,
    )


@pytest.mark.asyncio
async def test_permanent_failure_marks_post_failed_and_moves_job_to_dlq():
    job = make_job(
        post_id=100,
        user_id=200,
        attempts=1,
        job_id="socialpilot:post:100:mastodon",
    )

    (
        result,
        fake_post,
        fake_db,
        dlq_mock,
    ) = await run_permanent_failure_job(job)

    assert result is True

    assert fake_post.status == PostStatus.FAILED.value

    fake_db.commit.assert_awaited_once()

    dlq_mock.assert_awaited_once()

    call_kwargs = dlq_mock.await_args.kwargs

    assert call_kwargs["job_id"] == (
        "socialpilot:post:100:mastodon"
    )

    assert call_kwargs["failure_type"] == (
        "permanent_failure"
    )

    assert call_kwargs["error"] == (
        "Permanent platform failure."
    )


@pytest.mark.asyncio
async def test_retry_exhaustion_marks_post_failed_and_moves_job_to_dlq():
    job = make_job(
        post_id=101,
        user_id=201,
        attempts=retry_policy.max_attempts - 1,
        job_id="socialpilot:post:101:mastodon",
    )

    fake_post = make_fake_post(job["post_id"])

    retryable_error = ScheduledPublishError(
        "Retryable platform failure.",
        retryable=True,
    )

    with (
        patch(
            "app.worker.publisher.AsyncSessionLocal",
        ) as session_local_mock,
        patch(
            "app.worker.publisher.PostService.get_post",
            new=AsyncMock(return_value=fake_post),
        ),
        patch(
            "app.worker.publisher.PostService.publish_scheduled_post",
            new=AsyncMock(side_effect=retryable_error),
        ),
        patch(
            "app.worker.publisher.redis_queue.move_to_dead_letter",
            new=AsyncMock(return_value=True),
        ) as dlq_mock,
        patch(
            "app.worker.publisher.redis_queue.requeue_scheduled_post",
            new=AsyncMock(return_value=True),
        ) as requeue_mock,
    ):
        fake_db = AsyncMock()

        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_db
        session_context.__aexit__.return_value = None

        session_local_mock.return_value = session_context

        result = await process_job(job)

    assert result is True

    assert fake_post.status == PostStatus.FAILED.value

    fake_db.commit.assert_awaited_once()

    dlq_mock.assert_awaited_once()

    call_kwargs = dlq_mock.await_args.kwargs

    assert call_kwargs["job_id"] == (
        "socialpilot:post:101:mastodon"
    )

    assert call_kwargs["failure_type"] == (
        "retry_exhausted"
    )

    assert call_kwargs["error"] == (
        "Retryable platform failure."
    )

    requeue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_retryable_failure_before_max_attempts_goes_to_delayed_retry():
    job = make_job(
        post_id=102,
        user_id=202,
        attempts=1,
        job_id="socialpilot:post:102:mastodon",
    )

    fake_post = make_fake_post(job["post_id"])

    retryable_error = ScheduledPublishError(
        "Temporary platform failure.",
        retryable=True,
    )

    with (
        patch(
            "app.worker.publisher.AsyncSessionLocal",
        ) as session_local_mock,
        patch(
            "app.worker.publisher.PostService.get_post",
            new=AsyncMock(return_value=fake_post),
        ),
        patch(
            "app.worker.publisher.PostService.publish_scheduled_post",
            new=AsyncMock(side_effect=retryable_error),
        ),
        patch(
            "app.worker.publisher.redis_queue.requeue_scheduled_post",
            new=AsyncMock(return_value=True),
        ) as requeue_mock,
        patch(
            "app.worker.publisher.redis_queue.move_to_dead_letter",
            new=AsyncMock(return_value=True),
        ) as dlq_mock,
    ):
        fake_db = AsyncMock()

        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_db
        session_context.__aexit__.return_value = None

        session_local_mock.return_value = session_context

        result = await process_job(job)

    assert result is False

    assert fake_post.status == (
        PostStatus.PUBLISHING.value
    )

    requeue_mock.assert_awaited_once()

    call_kwargs = requeue_mock.await_args.kwargs

    assert call_kwargs["job_id"] == (
        "socialpilot:post:102:mastodon"
    )

    assert call_kwargs["attempts"] == 2

    dlq_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_dlq_failure_keeps_processing_job_unacknowledged():
    job = make_job(
        post_id=103,
        user_id=203,
        attempts=1,
        job_id="socialpilot:post:103:mastodon",
    )

    fake_post = make_fake_post(job["post_id"])

    permanent_error = ScheduledPublishError(
        "Permanent platform failure.",
        retryable=False,
    )

    with (
        patch(
            "app.worker.publisher.AsyncSessionLocal",
        ) as session_local_mock,
        patch(
            "app.worker.publisher.PostService.get_post",
            new=AsyncMock(return_value=fake_post),
        ),
        patch(
            "app.worker.publisher.PostService.publish_scheduled_post",
            new=AsyncMock(side_effect=permanent_error),
        ),
        patch(
            "app.worker.publisher.redis_queue.move_to_dead_letter",
            new=AsyncMock(return_value=False),
        ) as dlq_mock,
    ):
        fake_db = AsyncMock()

        session_context = AsyncMock()
        session_context.__aenter__.return_value = fake_db
        session_context.__aexit__.return_value = None

        session_local_mock.return_value = session_context

        result = await process_job(job)

    assert result is False

    assert fake_post.status == (
        PostStatus.FAILED.value
    )

    fake_db.commit.assert_awaited_once()

    dlq_mock.assert_awaited_once()

    call_kwargs = dlq_mock.await_args.kwargs

    assert call_kwargs["job_id"] == (
        "socialpilot:post:103:mastodon"
    )

    assert call_kwargs["failure_type"] == (
        "permanent_failure"
    )

    assert call_kwargs["error"] == (
        "Permanent platform failure."
    )