from app.integrations.mastodon.adapter import mastodon_adapter
from app.integrations.platforms.registry import platform_registry


def register_platforms() -> None:
    """
    Register all available social platform adapters.

    This function is intentionally explicit so adding a new platform
    requires registering its adapter here without modifying the publishing
    service.
    """

    if not platform_registry.supports(mastodon_adapter.platform):
        platform_registry.register(mastodon_adapter)