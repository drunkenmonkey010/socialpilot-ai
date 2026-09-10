from app.integrations.instagram.adapter import instagram_adapter
from app.integrations.mastodon.adapter import mastodon_adapter
from app.integrations.platforms.registry import platform_registry


def register_platforms() -> None:
    """
    Register all available social platform adapters.

    Adding a platform only requires registering its adapter here.
    PublicationService does not need platform-specific changes.
    """

    adapters = (
        mastodon_adapter,
        instagram_adapter,
    )

    for adapter in adapters:
        if not platform_registry.supports(adapter.platform):
            platform_registry.register(adapter)