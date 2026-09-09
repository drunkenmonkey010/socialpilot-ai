import pytest

from app.integrations.platforms.base import PlatformPublisher
from app.integrations.platforms.registry import PlatformRegistry
from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
)
from app.models.social_account import SocialAccount


class FakePublisher(PlatformPublisher):
    platform = "fake"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            text=True,
            images=False,
            video=False,
            carousel=False,
            scheduling=False,
            analytics=False,
            reconciliation=False,
            max_text_length=100,
        )

    async def publish(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str | None = None,
    ) -> PublicationResult:
        self.validate_content(content)

        return PublicationResult(
            platform=self.platform,
            external_post_id="fake-123",
            metadata={
                "publication_key": publication_key,
            },
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        return True


class SecondPublisher(PlatformPublisher):
    platform = "second"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            text=True,
            max_text_length=200,
        )

    async def publish(
        self,
        account: SocialAccount,
        content: str,
        publication_key: str | None = None,
    ) -> PublicationResult:
        return PublicationResult(
            platform=self.platform,
            external_post_id="second-123",
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        return True


def test_register_and_get_publisher():
    registry = PlatformRegistry()
    publisher = FakePublisher()

    registry.register(publisher)

    assert registry.get("fake") is publisher
    assert registry.supports("fake") is True


def test_platform_names_are_normalized():
    registry = PlatformRegistry()
    publisher = FakePublisher()

    registry.register(publisher)

    assert registry.get("FAKE") is publisher
    assert registry.get(" Fake ") is publisher
    assert registry.supports("FAKE") is True


def test_duplicate_platform_registration_is_rejected():
    registry = PlatformRegistry()

    registry.register(FakePublisher())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakePublisher())


def test_invalid_publisher_is_rejected():
    registry = PlatformRegistry()

    with pytest.raises(
        TypeError,
        match="Only PlatformPublisher implementations",
    ):
        registry.register(object())


def test_empty_platform_name_is_rejected():
    class EmptyPlatformPublisher(PlatformPublisher):
        platform = "   "

        @property
        def capabilities(self) -> PlatformCapabilities:
            return PlatformCapabilities()

        async def publish(
            self,
            account: SocialAccount,
            content: str,
            publication_key: str | None = None,
        ) -> PublicationResult:
            raise NotImplementedError

        def classify_error(
            self,
            exc: Exception,
        ) -> bool:
            return False

    registry = PlatformRegistry()

    with pytest.raises(
        ValueError,
        match="must define a platform name",
    ):
        registry.register(EmptyPlatformPublisher())


def test_empty_platform_lookup_is_rejected():
    registry = PlatformRegistry()

    with pytest.raises(
        ValueError,
        match="Platform name cannot be empty",
    ):
        registry.get("   ")


def test_unsupported_platform_is_rejected():
    registry = PlatformRegistry()

    with pytest.raises(
        ValueError,
        match="No publisher registered",
    ):
        registry.get("instagram")


def test_platform_support_and_listing():
    registry = PlatformRegistry()

    registry.register(FakePublisher())
    registry.register(SecondPublisher())

    assert registry.supports("fake") is True
    assert registry.supports("second") is True
    assert registry.supports("instagram") is False

    assert registry.platforms() == (
        "fake",
        "second",
    )


def test_validate_content_rejects_empty_content():
    publisher = FakePublisher()

    with pytest.raises(
        ValueError,
        match="content cannot be empty",
    ):
        publisher.validate_content("")


def test_validate_content_rejects_content_over_limit():
    publisher = FakePublisher()

    content = "a" * 101

    with pytest.raises(
        ValueError,
        match="maximum length of 100",
    ):
        publisher.validate_content(content)


def test_validate_content_accepts_valid_content():
    publisher = FakePublisher()

    publisher.validate_content("Hello SocialPilot AI")
