class PlatformError(Exception):
    """Base exception for platform integration failures."""


class PlatformConfigurationError(PlatformError):
    """Raised when a platform integration is incorrectly configured."""


class PlatformAuthenticationError(PlatformError):
    """Raised when platform authentication is invalid or unavailable."""


class PlatformValidationError(PlatformError):
    """Raised when content cannot be published to a platform."""


class PlatformRateLimitError(PlatformError):
    """
    Raised when a platform rate-limits a publication request.

    retry_after_seconds contains the platform-provided delay when
    available. It is None when the platform did not provide a usable
    Retry-After value.
    """

    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)

        self.retry_after_seconds = retry_after_seconds


class PlatformTransientError(PlatformError):
    """Raised when a platform failure may succeed if retried."""


class PlatformPermanentError(PlatformError):
    """Raised when a platform failure should not be retried automatically."""