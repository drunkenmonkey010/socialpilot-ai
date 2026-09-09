from abc import ABC, abstractmethod

from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
    ReconciliationResult,
)
from app.models.social_account import SocialAccount


class PlatformPublisher(ABC):
    """
    Generic contract for social media publishing integrations.

    The application core interacts with this interface instead of directly
    depending on a platform-specific API.
    """

    platform: str

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        """Return capabilities supported by this platform."""

    def validate_content(
        self,
        content: str,
    ) -> None:
        """
        Perform generic capability-based content validation.

        Platform-specific API validation remains inside the adapter.
        """

        if not content or not content.strip():
            raise ValueError(
                f"{self.platform} content cannot be empty."
            )

        capabilities = self.capabilities

        if not capabilities.text:
            raise ValueError(
                f"{self.platform} does not support text publications."
            )

        if (
            capabilities.max_text_length is not None
            and len(content) > capabilities.max_text_length
        ):
            raise ValueError(
                f"{self.platform} content exceeds the maximum "
                f"length of {capabilities.max_text_length} characters."
            )

    @abstractmethod
    async def publish(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str | None = None,
    ) -> PublicationResult:
        """
        Publish content to the platform.

        publication_key is a stable application-level identity for the
        publication attempt. Platforms may use it for native idempotency
        where supported.
        """

    async def reconcile(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str,
    ) -> ReconciliationResult:
        """
        Determine whether a previous publication succeeded.

        Platforms that provide reliable reconciliation should override this
        method.

        By default, reconciliation is unavailable.
        """

        return ReconciliationResult(
            found=False,
            metadata={
                "supported": False,
                "publication_key": publication_key,
            },
        )

    @abstractmethod
    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        """
        Determine whether a platform exception is retryable.

        Returns:

            True  -> retry may succeed.
            False -> failure should be treated as permanent.
        """