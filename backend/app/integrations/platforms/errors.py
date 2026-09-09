class PlatformError(Exception):
    """Base exception for platform integration failures."""


class PlatformConfigurationError(PlatformError):
    """Raised when a platform integration is incorrectly configured."""


class PlatformAuthenticationError(PlatformError):
    """Raised when platform authentication is invalid or unavailable."""


class PlatformValidationError(PlatformError):
    """Raised when content cannot be published to a platform."""


class PlatformRateLimitError(PlatformError):
    """Raised when a platform rate-limits a publication request."""


class PlatformTransientError(PlatformError):
    """
    Raised when a platform failure may succeed if the operation is retried.
    """


class PlatformPermanentError(PlatformError):
    """
    Raised when a platform failure should not be retried automatically.
    """