import pytest

from app.integrations.platforms.base import PlatformPublisher
from app.integrations.platforms.errors import (
    PlatformPermanentError,
    PlatformRateLimitError,
    PlatformTransientError,
)
from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
)
from app.integrations.mastodon.adapter import MastodonAdapter
from app.models.social_account import SocialAccount


class ContractTestPublisher(PlatformPublisher):
    """Minimal publisher used to verify the generic platform contract."""

    platform = "contract_test"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            text=True,
            images=True,
            video=True,
            carousel=True,
            scheduling=True,
            analytics=True,
            reconciliation=True,
            max_text_length=280,
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
            external_post_id="contract-test-123",
            metadata={
                "publication_key": publication_key,
            },
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        return isinstance(
            exc,
            (
                PlatformTransientError,
                PlatformRateLimitError,
            ),
        )


def test_platform_contract_exposes_capabilities():
    publisher = ContractTestPublisher()

    assert publisher.capabilities.text is True
    assert publisher.capabilities.images is True
    assert publisher.capabilities.video is True
    assert publisher.capabilities.carousel is True
    assert publisher.capabilities.scheduling is True
    assert publisher.capabilities.analytics is True
    assert publisher.capabilities.reconciliation is True
    assert publisher.capabilities.max_text_length == 280


def test_platform_contract_validates_empty_content():
    publisher = ContractTestPublisher()

    with pytest.raises(
        Exception,
        match="content cannot be empty",
    ):
        publisher.validate_content("")


def test_platform_contract_validates_max_text_length():
    publisher = ContractTestPublisher()

    with pytest.raises(
        Exception,
        match="maximum length of 280",
    ):
        publisher.validate_content("a" * 281)


@pytest.mark.asyncio
async def test_platform_contract_returns_publication_result():
    publisher = ContractTestPublisher()

    result = await publisher.publish(
        account=object(),
        content="Hello SocialPilot AI",
        publication_key="test-publication-key",
    )

    assert result.platform == "contract_test"
    assert result.external_post_id == "contract-test-123"
    assert result.metadata["publication_key"] == (
        "test-publication-key"
    )


def test_platform_contract_classifies_transient_errors_as_retryable():
    publisher = ContractTestPublisher()

    assert publisher.classify_error(
        PlatformTransientError("temporary failure")
    ) is True


def test_platform_contract_classifies_rate_limits_as_retryable():
    publisher = ContractTestPublisher()

    assert publisher.classify_error(
        PlatformRateLimitError(
            "rate limited",
            retry_after_seconds=30,
        )
    ) is True


def test_platform_contract_classifies_permanent_errors_as_non_retryable():
    publisher = ContractTestPublisher()

    assert publisher.classify_error(
        PlatformPermanentError("invalid request")
    ) is False


def test_mastodon_adapter_implements_generic_platform_contract():
    publisher = MastodonAdapter()

    assert isinstance(
        publisher,
        PlatformPublisher,
    )

    assert publisher.platform == "mastodon"

    assert publisher.capabilities.text is True
    assert publisher.capabilities.images is False
    assert publisher.capabilities.video is False
    assert publisher.capabilities.carousel is False
    assert publisher.capabilities.reconciliation is False
    assert publisher.capabilities.max_text_length == 500