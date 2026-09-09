from app.integrations.platforms.base import PlatformPublisher


class PlatformRegistry:
    """
    Registry of available social media platform publishers.

    Platform names are normalized to lowercase so callers can safely use
    values such as "Mastodon", "MASTODON", or "mastodon".
    """

    def __init__(self) -> None:
        self._publishers: dict[str, PlatformPublisher] = {}

    def register(
        self,
        publisher: PlatformPublisher,
    ) -> None:
        """Register a platform publisher."""

        platform = publisher.platform.lower().strip()

        if not platform:
            raise ValueError(
                "Platform publisher must define a platform name."
            )

        if platform in self._publishers:
            raise ValueError(
                f"Platform publisher already registered: '{platform}'."
            )

        self._publishers[platform] = publisher

    def get(
        self,
        platform: str,
    ) -> PlatformPublisher:
        """Return the publisher registered for a platform."""

        normalized_platform = platform.lower().strip()

        publisher = self._publishers.get(normalized_platform)

        if publisher is None:
            raise ValueError(
                f"No publisher registered for platform "
                f"'{platform}'."
            )

        return publisher

    def supports(
        self,
        platform: str,
    ) -> bool:
        """Return whether a platform publisher is registered."""

        return platform.lower().strip() in self._publishers

    def platforms(self) -> tuple[str, ...]:
        """Return all registered platform names."""

        return tuple(sorted(self._publishers))


platform_registry = PlatformRegistry()