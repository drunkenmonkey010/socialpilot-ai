import pytest

from app.worker.retry import RetryPolicy


def test_exponential_backoff() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=30,
        max_backoff_seconds=900,
        jitter_ratio=0,
    )

    assert policy.calculate_backoff(1) == 30
    assert policy.calculate_backoff(2) == 60
    assert policy.calculate_backoff(3) == 120
    assert policy.calculate_backoff(4) == 240
    assert policy.calculate_backoff(5) == 480


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=30,
        max_backoff_seconds=100,
        jitter_ratio=0,
    )

    assert policy.calculate_backoff(1) == 30
    assert policy.calculate_backoff(2) == 60
    assert policy.calculate_backoff(3) == 100
    assert policy.calculate_backoff(10) == 100


def test_zero_jitter_returns_base_delay() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=30,
        max_backoff_seconds=900,
        jitter_ratio=0,
    )

    assert policy.calculate_retry_delay(1) == 30
    assert policy.calculate_retry_delay(2) == 60
    assert policy.calculate_retry_delay(3) == 120


def test_jitter_stays_within_expected_range() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=100,
        max_backoff_seconds=900,
        jitter_ratio=0.20,
    )

    for _ in range(100):
        delay = policy.calculate_retry_delay(1)

        assert 80 <= delay <= 120


def test_jitter_respects_maximum_backoff() -> None:
    policy = RetryPolicy(
        initial_backoff_seconds=100,
        max_backoff_seconds=110,
        jitter_ratio=0.20,
    )

    for _ in range(100):
        delay = policy.calculate_retry_delay(1)

        assert delay <= 110


def test_invalid_attempt_is_rejected() -> None:
    policy = RetryPolicy()

    with pytest.raises(ValueError):
        policy.calculate_backoff(0)

    with pytest.raises(ValueError):
        policy.calculate_retry_delay(0)


def test_invalid_jitter_ratio_is_rejected() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(jitter_ratio=-0.1)

    with pytest.raises(ValueError):
        RetryPolicy(jitter_ratio=1.1)