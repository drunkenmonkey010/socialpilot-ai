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

    Every supported social platform implements this interface.

    The application core interacts with this contract rather than directly
    depending on a specific platform API.
    """

    platform: str

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        """Return capabilities supported by this platform."""

    @abstractmethod
    async def publish(
        self,
        account: SocialAccount,
        content: str,
    ) -> PublicationResult:
        """
        Publish content to the platform.

        Platform-specific API details must remain inside the adapter.
        """

    async def reconcile(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str,
    ) -> ReconciliationResult:
        """
        Attempt to determine whether a previous publication succeeded.

        Platforms that support reliable reconciliation should override this
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