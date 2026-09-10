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
    job = {
        "job_id": "socialpilot:post:123:mastodon",
        "post_id": 123,
        "user_id": 456,
        "attempts": 0,
    }

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
    job = {
        "job_id": "socialpilot:post:456:mastodon",
        "post_id": 456,
        "user_id": 789,
        "attempts": 1,
    }

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
    job = {
        "job_id": "socialpilot:post:789:mastodon",
        "post_id": 789,
        "user_id": 101,
        "attempts": 0,
    }

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