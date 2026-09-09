from app.integrations.mastodon.oauth import publish_mastodon_status
from app.integrations.platforms.base import PlatformPublisher
from app.integrations.platforms.errors import (
    PlatformAuthenticationError,
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
    PlatformValidationError,
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

        Media support will be enabled only after the adapter implements
        actual media upload/publication handling.
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

        try:
            self.validate_content(content)
        except ValueError as exc:
            raise PlatformValidationError(str(exc)) from exc

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

        The adapter owns interpretation of Mastodon's API failures.
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
                PlatformValidationError,
                PlatformPermanentError,
            ),
        ):
            return False

        return True

    @staticmethod
    def _translate_error(
        exc: Exception,
    ) -> Exception:
        """
        Translate Mastodon-specific failures into generic platform errors.
        """

        if isinstance(
            exc,
            (
                TimeoutError,
                ConnectionError,
            ),
        ):
            return PlatformTransientError(str(exc))

        message = str(exc)

        status_codes = [
            code
            for code in range(100, 600)
            if f" {code} " in message
            or f" {code}:" in message
        ]

        if not status_codes:
            return PlatformTransientError(message)

        status_code = status_codes[0]

        if status_code == 401 or status_code == 403:
            return PlatformAuthenticationError(message)

        if status_code == 429:
            return PlatformRateLimitError(message)

        if 400 <= status_code <= 499:
            return PlatformPermanentError(message)

        if 500 <= status_code <= 599:
            return PlatformTransientError(message)

        return PlatformPermanentError(message)


mastodon_adapter = MastodonAdapter()