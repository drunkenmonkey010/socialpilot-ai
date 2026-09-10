import httpx

from app.integrations.mastodon.oauth import publish_mastodon_status
from app.integrations.platforms.base import PlatformPublisher
from app.integrations.platforms.errors import (
    PlatformAuthenticationError,
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
)
from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
)
from app.models.social_account import SocialAccount


class MastodonAdapter(PlatformPublisher):
    """
    Mastodon implementation of the generic publishing contract.

    Mastodon-specific API behavior and error interpretation remain inside
    this adapter.
    """

    platform = "mastodon"

    @property
    def capabilities(self) -> PlatformCapabilities:
        """
        Return capabilities currently implemented by this adapter.
        """

        return PlatformCapabilities(
            text=True,
            images=False,
            video=False,
            carousel=False,
            scheduling=False,
            analytics=False,
            reconciliation=False,
            max_text_length=500,
        )

    async def publish(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str | None = None,
    ) -> PublicationResult:
        """Publish text content through Mastodon's API."""

        if not account.access_token:
            raise PlatformAuthenticationError(
                "Mastodon access token is required."
            )

        self.validate_content(content)

        try:
            response = await publish_mastodon_status(
                access_token=account.access_token,
                content=content,
            )

        except Exception as exc:
            raise self._translate_error(exc) from exc

        external_post_id = response.get("id")

        if not external_post_id:
            raise PlatformTransientError(
                "Mastodon returned a successful response "
                "without a status ID."
            )

        return PublicationResult(
            platform=self.platform,
            external_post_id=str(external_post_id),
            metadata={
                "response": response,
                "publication_key": publication_key,
            },
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        """
        Return whether a Mastodon error should be retried.
        """

        if isinstance(
            exc,
            (
                PlatformTransientError,
                PlatformRateLimitError,
            ),
        ):
            return True

        if isinstance(
            exc,
            (
                PlatformAuthenticationError,
                PlatformPermanentError,
            ),
        ):
            return False

        return True

    @staticmethod
    def _parse_retry_after(
        response: httpx.Response,
    ) -> int | None:
        """
        Parse the Retry-After response header.

        Supports the standard integer-seconds form.

        Invalid, missing, or non-positive values are ignored so the
        worker can fall back to normal exponential backoff.
        """

        retry_after = response.headers.get(
            "Retry-After",
        )

        if retry_after is None:
            return None

        try:
            seconds = int(
                retry_after.strip(),
            )
        except ValueError:
            return None

        if seconds <= 0:
            return None

        return seconds

    @staticmethod
    def _translate_error(
        exc: Exception,
    ) -> Exception:
        """
        Translate Mastodon-specific failures into generic platform errors.
        """

        if isinstance(
            exc,
            httpx.HTTPStatusError,
        ):
            response = exc.response
            status_code = response.status_code
            message = str(exc)

            if status_code in (401, 403):
                return PlatformAuthenticationError(
                    message,
                )

            if status_code == 429:
                return PlatformRateLimitError(
                    message,
                    retry_after_seconds=(
                        MastodonAdapter._parse_retry_after(
                            response,
                        )
                    ),
                )

            if 400 <= status_code <= 499:
                return PlatformPermanentError(
                    message,
                )

            if 500 <= status_code <= 599:
                return PlatformTransientError(
                    message,
                )

        if isinstance(
            exc,
            (
                TimeoutError,
                ConnectionError,
                httpx.TimeoutException,
                httpx.NetworkError,
            ),
        ):
            return PlatformTransientError(
                str(exc),
            )

        message = str(exc)

        status_codes = [
            code
            for code in range(100, 600)
            if f" {code} " in message
            or f" {code}:" in message
        ]

        if not status_codes:
            return PlatformTransientError(
                message,
            )

        status_code = status_codes[0]

        if status_code in (401, 403):
            return PlatformAuthenticationError(
                message,
            )

        if status_code == 429:
            return PlatformRateLimitError(
                message,
            )

        if 400 <= status_code <= 499:
            return PlatformPermanentError(
                message,
            )

        if 500 <= status_code <= 599:
            return PlatformTransientError(
                message,
            )

        return PlatformPermanentError(
            message,
        )


mastodon_adapter = MastodonAdapter()