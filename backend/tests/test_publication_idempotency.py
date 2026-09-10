from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.platforms.types import (
    PlatformCapabilities,
    PublicationResult,
    ReconciliationResult,
)
from app.models.post import PostStatus
from app.services.publication import PublicationService


class ReconcilablePublisher:
    platform = "fake_idempotent"

    def __init__(
        self,
        reconciliation_result: ReconciliationResult,
    ):
        self.reconciliation_result = reconciliation_result
        self.reconcile_calls = 0
        self.publish_calls = 0

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            text=True,
            reconciliation=True,
            max_text_length=500,
        )

    def validate_content(
        self,
        content: str,
    ) -> None:
        if not content:
            raise ValueError("Content cannot be empty.")

    async def reconcile(
        self,
        account,
        content,
        publication_key,
    ) -> ReconciliationResult:
        self.reconcile_calls += 1

        return self.reconciliation_result

    async def publish(
        self,
        account,
        content,
        publication_key=None,
    ) -> PublicationResult:
        self.publish_calls += 1

        return PublicationResult(
            platform=self.platform,
            external_post_id="new-external-123",
            metadata={
                "publication_key": publication_key,
            },
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        return True


class NonReconcilablePublisher:
    platform = "fake_non_reconcilable"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            text=True,
            reconciliation=False,
            max_text_length=500,
        )

    def validate_content(
        self,
        content: str,
    ) -> None:
        if not content:
            raise ValueError("Content cannot be empty.")

    async def reconcile(
        self,
        account,
        content,
        publication_key,
    ) -> ReconciliationResult:
        raise AssertionError(
            "Reconcile must not be called for an unsupported platform."
        )

    async def publish(
        self,
        account,
        content,
        publication_key=None,
    ) -> PublicationResult:
        return PublicationResult(
            platform=self.platform,
            external_post_id="new-external-456",
        )

    def classify_error(
        self,
        exc: Exception,
    ) -> bool:
        return True


class FailingReconcilablePublisher(ReconcilablePublisher):
    async def reconcile(
        self,
        account,
        content,
        publication_key,
    ) -> ReconciliationResult:
        self.reconcile_calls += 1

        raise RuntimeError(
            "reconciliation service unavailable"
        )


def make_post(
    attempts: int = 1,
    external_post_id: str | None = None,
):
    return type(
        "FakePost",
        (),
        {
            "id": 100,
            "content": "Idempotency test post",
            "platform": "fake_idempotent",
            "status": PostStatus.PUBLISHING.value,
            "publication_attempts": attempts,
            "publication_key": "socialpilot:post:100:fake_idempotent",
            "external_post_id": external_post_id,
            "published_at": None,
        },
    )()


@pytest.mark.asyncio
async def test_retry_reconciles_existing_publication_without_republishing():
    publisher = ReconcilablePublisher(
        ReconciliationResult(
            found=True,
            external_post_id="existing-external-123",
        )
    )

    post = make_post(
        attempts=1,
    )

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.publication.PostRepository.record_publication_result",
            new=AsyncMock(return_value=post),
        ) as record_mock,
    ):
        fake_db = AsyncMock()

        result = await PublicationService.publish(
            fake_db,
            post,
            user_id=1,
        )

    assert result is post
    assert publisher.reconcile_calls == 1
    assert publisher.publish_calls == 0

    record_mock.assert_awaited_once_with(
        fake_db,
        post.id,
        "existing-external-123",
    )


@pytest.mark.asyncio
async def test_retry_publishes_when_reconciliation_does_not_find_publication():
    publisher = ReconcilablePublisher(
        ReconciliationResult(
            found=False,
        )
    )

    post = make_post(
        attempts=1,
    )

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.publication.PostRepository.increment_publication_attempts",
            new=AsyncMock(return_value=2),
        ),
        patch(
            "app.services.publication.PostRepository.record_publication_result",
            new=AsyncMock(return_value=post),
        ),
    ):
        fake_db = AsyncMock()

        result = await PublicationService.publish(
            fake_db,
            post,
            user_id=1,
        )

    assert result is post
    assert publisher.reconcile_calls == 1
    assert publisher.publish_calls == 1


@pytest.mark.asyncio
async def test_first_attempt_does_not_reconcile():
    publisher = ReconcilablePublisher(
        ReconciliationResult(
            found=True,
            external_post_id="should-not-be-used",
        )
    )

    post = make_post(
        attempts=0,
    )

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.publication.PostRepository.increment_publication_attempts",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "app.services.publication.PostRepository.record_publication_result",
            new=AsyncMock(return_value=post),
        ),
    ):
        fake_db = AsyncMock()

        result = await PublicationService.publish(
            fake_db,
            post,
            user_id=1,
        )

    assert result is post
    assert publisher.reconcile_calls == 0
    assert publisher.publish_calls == 1


@pytest.mark.asyncio
async def test_existing_external_id_skips_reconciliation_and_publication():
    publisher = ReconcilablePublisher(
        ReconciliationResult(
            found=True,
            external_post_id="should-not-be-called",
        )
    )

    post = make_post(
        attempts=1,
        external_post_id="already-published-123",
    )

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
    ):
        fake_db = AsyncMock()

        result = await PublicationService.publish(
            fake_db,
            post,
            user_id=1,
        )

    assert result is post
    assert publisher.reconcile_calls == 0
    assert publisher.publish_calls == 0


@pytest.mark.asyncio
async def test_unsupported_reconciliation_preserves_existing_behavior():
    publisher = NonReconcilablePublisher()

    post = make_post(
        attempts=1,
    )

    post.platform = "fake_non_reconcilable"

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.publication.PostRepository.increment_publication_attempts",
            new=AsyncMock(return_value=2),
        ),
        patch(
            "app.services.publication.PostRepository.record_publication_result",
            new=AsyncMock(return_value=post),
        ),
    ):
        fake_db = AsyncMock()

        result = await PublicationService.publish(
            fake_db,
            post,
            user_id=1,
        )

    assert result is post


@pytest.mark.asyncio
async def test_reconciliation_failure_does_not_publish():
    publisher = FailingReconcilablePublisher(
        ReconciliationResult(
            found=False,
        )
    )

    post = make_post(
        attempts=1,
    )

    fake_account = object()

    with (
        patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ),
        patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.publication.PostRepository.increment_publication_attempts",
            new=AsyncMock(return_value=2),
        ),
        patch(
            "app.services.publication.PostRepository.record_publication_result",
            new=AsyncMock(return_value=post),
        ),
    ):
        fake_db = AsyncMock()

        with pytest.raises(
            Exception,
            match="Publication reconciliation failed",
        ):
            await PublicationService.publish(
                fake_db,
                post,
                user_id=1,
            )

    assert publisher.reconcile_calls == 1
    assert publisher.publish_calls == 0