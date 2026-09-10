import httpx

from app.integrations.mastodon.adapter import MastodonAdapter
from app.integrations.platforms.errors import (
    PlatformAuthenticationError,
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
)


def make_http_error(
    status_code: int,
    headers: dict[str, str] | None = None,
) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "POST",
        "https://mastodon.example/api/v1/statuses",
    )

    response = httpx.Response(
        status_code,
        request=request,
        headers=headers,
    )

    return httpx.HTTPStatusError(
        message=f"Mastodon request failed: {status_code}",
        request=request,
        response=response,
    )


def test_retry_after_is_parsed() -> None:
    error = make_http_error(
        429,
        headers={
            "Retry-After": "120",
        },
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformRateLimitError,
    )

    assert translated.retry_after_seconds == 120


def test_missing_retry_after_returns_none() -> None:
    error = make_http_error(
        429,
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformRateLimitError,
    )

    assert translated.retry_after_seconds is None


def test_invalid_retry_after_returns_none() -> None:
    error = make_http_error(
        429,
        headers={
            "Retry-After": "not-a-number",
        },
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformRateLimitError,
    )

    assert translated.retry_after_seconds is None


def test_non_positive_retry_after_returns_none() -> None:
    for value in ("0", "-10"):
        error = make_http_error(
            429,
            headers={
                "Retry-After": value,
            },
        )

        translated = MastodonAdapter._translate_error(
            error,
        )

        assert isinstance(
            translated,
            PlatformRateLimitError,
        )

        assert translated.retry_after_seconds is None


def test_rate_limit_is_retryable() -> None:
    adapter = MastodonAdapter()

    error = PlatformRateLimitError(
        "Rate limited",
        retry_after_seconds=120,
    )

    assert adapter.classify_error(error) is True


def test_authentication_error_is_not_retryable() -> None:
    error = make_http_error(
        401,
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformAuthenticationError,
    )

    assert MastodonAdapter().classify_error(
        translated,
    ) is False


def test_client_error_other_than_rate_limit_is_permanent() -> None:
    error = make_http_error(
        400,
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformPermanentError,
    )

    assert MastodonAdapter().classify_error(
        translated,
    ) is False


def test_server_error_is_retryable() -> None:
    error = make_http_error(
        503,
    )

    translated = MastodonAdapter._translate_error(
        error,
    )

    assert isinstance(
        translated,
        PlatformTransientError,
    )

    assert MastodonAdapter().classify_error(
        translated,
    ) is True