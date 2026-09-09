from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlatformCapabilities:
    """
    Capabilities supported by a social media platform.

    These capabilities allow the application core to remain platform-neutral
    while individual platforms can expose their own limitations.
    """

    text: bool = True
    images: bool = False
    video: bool = False
    carousel: bool = False
    scheduling: bool = False
    analytics: bool = False
    reconciliation: bool = False

    max_text_length: int | None = None


@dataclass(frozen=True)
class PublicationResult:
    """
    Generic result returned by a platform publication adapter.

    The core application does not need to know the shape of the platform's
    raw API response.
    """

    platform: str
    external_post_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconciliationResult:
    """
    Generic result for determining whether a publication already exists
    on a platform.
    """

    found: bool
    external_post_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)