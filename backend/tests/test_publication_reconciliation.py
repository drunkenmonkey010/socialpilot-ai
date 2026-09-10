from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.repositories.post import PostRepository
from app.services.publication import PublicationService


class FakeReconciliationPublisher:
    platform = "fake"

    def validate_content(self, content: str) -> None:
        return None

    async def publish(
        self,
        account,
        content: str,
        publication_key: str | None = None,
    ):
        raise AssertionError(
            "publish() must not be called during reconciliation."
        )

    async def reconcile(
        self,
        account,
        content: str,
        publication_key: str,
    ):
        from app.integrations.platforms.types import (
            ReconciliationResult,
        )

        return ReconciliationResult(
            found=True,
            external_post_id="external-reconciled-123",
            metadata={
                "publication_key": publication_key,
            },
        )

    def classify_error(self, exc: Exception) -> bool:
        return True


async def create_reconciliation_post(
    user_id: int,
) -> Post:
    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=user_id,
            name="Reconciliation Test Brand",
            description="Reconciliation test brand",
        )

        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name="Reconciliation Test Campaign",
            description="Reconciliation test campaign",
        )

        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Reconciliation test content",
            platform="fake",
            status=PostStatus.PUBLISHING.value,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        return post


async def cleanup_reconciliation_post(
    post_id: int,
) -> None:
    async with AsyncSessionLocal() as db:
        post = await PostRepository.get_by_id(
            db,
            post_id,
        )

        if post is None:
            return

        campaign = await db.get(
            Campaign,
            post.campaign_id,
        )

        if campaign is None:
            return

        brand = await db.get(
            Brand,
            campaign.brand_id,
        )

        await db.delete(post)
        await db.flush()

        await db.delete(campaign)
        await db.flush()

        if brand is not None:
            await db.delete(brand)

        await db.commit()


@pytest.mark.asyncio
async def test_reconciliation_persists_external_publication(
    test_user,
):
    post = await create_reconciliation_post(
        test_user["id"],
    )

    try:
        publisher = FakeReconciliationPublisher()

        fake_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.publication.PublicationService.get_publisher",
                return_value=publisher,
            ),
            patch(
                "app.services.publication.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(
                    return_value=fake_account,
                ),
            ),
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(
                    db,
                    post.id,
                )

                assert db_post is not None

                result = await PublicationService.reconcile(
                    db,
                    db_post,
                    test_user["id"],
                )

                assert result.found is True
                assert result.external_post_id == (
                    "external-reconciled-123"
                )

        async with AsyncSessionLocal() as db:
            persisted = await PostRepository.get_by_id(
                db,
                post.id,
            )

            assert persisted is not None
            assert persisted.status == (
                PostStatus.PUBLISHED.value
            )
            assert persisted.external_post_id == (
                "external-reconciled-123"
            )
            assert persisted.published_at is not None
            assert persisted.publication_key == (
                f"socialpilot:post:{post.id}:fake"
            )

    finally:
        await cleanup_reconciliation_post(
            post.id,
        )


@pytest.mark.asyncio
async def test_reconciliation_does_not_publish_again(
    test_user,
):
    post = await create_reconciliation_post(
        test_user["id"],
    )

    try:
        publisher = FakeReconciliationPublisher()

        fake_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.publication.PublicationService.get_publisher",
                return_value=publisher,
            ),
            patch(
                "app.services.publication.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(
                    return_value=fake_account,
                ),
            ),
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(
                    db,
                    post.id,
                )

                assert db_post is not None

                result = await PublicationService.reconcile(
                    db,
                    db_post,
                    test_user["id"],
                )

                assert result.found is True

                persisted = await PostRepository.get_by_id(
                    db,
                    post.id,
                )

                assert persisted is not None
                assert persisted.external_post_id == (
                    "external-reconciled-123"
                )

    finally:
        await cleanup_reconciliation_post(
            post.id,
        )