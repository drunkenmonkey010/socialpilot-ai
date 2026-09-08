import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.repositories.post import PostRepository
from app.services.post import PostService, ScheduledPublishError


async def create_test_post(
    user_id: int,
    status: str = PostStatus.PUBLISHING.value,
    external_post_id: str | None = None,
) -> Post:
    """Create a post and its parent records for service tests."""

    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=user_id,
            name=f"Service Test Brand {uuid.uuid4().hex[:8]}",
            description="Post service test brand",
        )
        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name=f"Service Test Campaign {uuid.uuid4().hex[:8]}",
            description="Post service test campaign",
        )
        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Service idempotency test",
            platform="mastodon",
            status=status,
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            external_post_id=external_post_id,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        return post


async def cleanup_post(post_id: int) -> None:
    """Delete the post and its parent records created by a test."""

    async with AsyncSessionLocal() as db:
        post = await PostRepository.get_by_id(db, post_id)

        if post is None:
            return

        campaign = await db.get(Campaign, post.campaign_id)

        if campaign is None:
            return

        brand = await db.get(Brand, campaign.brand_id)

        await db.delete(post)
        await db.flush()

        await db.delete(campaign)
        await db.flush()

        if brand is not None:
            await db.delete(brand)

        await db.commit()


async def get_post(post_id: int) -> Post | None:
    """Reload a post from the database."""

    async with AsyncSessionLocal() as db:
        return await PostRepository.get_by_id(db, post_id)


@pytest.mark.asyncio
async def test_first_scheduled_publication_persists_idempotency_state(
    test_user,
):
    post = await create_test_post(test_user["id"])

    try:
        fake_social_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.post.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(return_value=fake_social_account),
            ),
            patch(
                "app.services.post.publish_mastodon_status",
                new=AsyncMock(return_value={"id": "mastodon-status-123"}),
            ) as publish_mock,
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(db, post.id)

                assert db_post is not None

                result = await PostService.publish_scheduled_post(
                    db,
                    db_post,
                    test_user["id"],
                )

                assert result.status == PostStatus.PUBLISHED.value
                assert result.external_post_id == "mastodon-status-123"
                assert result.publication_key == (
                    f"socialpilot:post:{post.id}:mastodon"
                )
                assert result.publication_attempts == 1
                assert result.published_at is not None

                publish_mock.assert_awaited_once()

        persisted = await get_post(post.id)

        assert persisted is not None
        assert persisted.status == PostStatus.PUBLISHED.value
        assert persisted.external_post_id == "mastodon-status-123"
        assert persisted.publication_key == (
            f"socialpilot:post:{post.id}:mastodon"
        )
        assert persisted.publication_attempts == 1

    finally:
        await cleanup_post(post.id)


@pytest.mark.asyncio
async def test_already_published_post_is_not_published_again(
    test_user,
):
    post = await create_test_post(
        test_user["id"],
        status=PostStatus.PUBLISHING.value,
        external_post_id="mastodon-existing-123",
    )

    try:
        fake_social_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.post.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(return_value=fake_social_account),
            ),
            patch(
                "app.services.post.publish_mastodon_status",
                new=AsyncMock(),
            ) as publish_mock,
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(db, post.id)

                assert db_post is not None

                result = await PostService.publish_scheduled_post(
                    db,
                    db_post,
                    test_user["id"],
                )

                assert result.status == PostStatus.PUBLISHED.value
                assert result.external_post_id == "mastodon-existing-123"

                publish_mock.assert_not_awaited()

        persisted = await get_post(post.id)

        assert persisted is not None
        assert persisted.status == PostStatus.PUBLISHED.value
        assert persisted.external_post_id == "mastodon-existing-123"
        assert persisted.publication_attempts == 0

    finally:
        await cleanup_post(post.id)


@pytest.mark.asyncio
async def test_transient_publication_failure_is_retryable(
    test_user,
):
    post = await create_test_post(test_user["id"])

    try:
        fake_social_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.post.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(return_value=fake_social_account),
            ),
            patch(
                "app.services.post.publish_mastodon_status",
                new=AsyncMock(
                    side_effect=RuntimeError(
                        "Mastodon status publication failed: 500 server error"
                    )
                ),
            ) as publish_mock,
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(db, post.id)

                assert db_post is not None

                with pytest.raises(ScheduledPublishError) as exc_info:
                    await PostService.publish_scheduled_post(
                        db,
                        db_post,
                        test_user["id"],
                    )

                assert exc_info.value.retryable is True
                publish_mock.assert_awaited_once()

        persisted = await get_post(post.id)

        assert persisted is not None
        assert persisted.status == PostStatus.PUBLISHING.value
        assert persisted.publication_attempts == 1
        assert persisted.external_post_id is None
        assert persisted.publication_key == (
            f"socialpilot:post:{post.id}:mastodon"
        )

    finally:
        await cleanup_post(post.id)


@pytest.mark.asyncio
async def test_permanent_publication_failure_marks_post_failed(
    test_user,
):
    post = await create_test_post(test_user["id"])

    try:
        fake_social_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        with (
            patch(
                "app.services.post.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(return_value=fake_social_account),
            ),
            patch(
                "app.services.post.publish_mastodon_status",
                new=AsyncMock(
                    side_effect=RuntimeError(
                        "Mastodon status publication failed: 401 unauthorized"
                    )
                ),
            ) as publish_mock,
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(db, post.id)

                assert db_post is not None

                with pytest.raises(ScheduledPublishError) as exc_info:
                    await PostService.publish_scheduled_post(
                        db,
                        db_post,
                        test_user["id"],
                    )

                assert exc_info.value.retryable is False
                publish_mock.assert_awaited_once()

        persisted = await get_post(post.id)

        assert persisted is not None
        assert persisted.status == PostStatus.FAILED.value
        assert persisted.publication_attempts == 1
        assert persisted.external_post_id is None

    finally:
        await cleanup_post(post.id)


@pytest.mark.asyncio
async def test_retry_after_transient_failure_publishes_once(
    test_user,
):
    post = await create_test_post(test_user["id"])

    try:
        fake_social_account = type(
            "FakeSocialAccount",
            (),
            {
                "access_token": "test-token",
                "is_active": True,
            },
        )()

        publish_mock = AsyncMock(
            side_effect=[
                RuntimeError(
                    "Mastodon status publication failed: 500 server error"
                ),
                {"id": "mastodon-status-retry-456"},
            ]
        )

        with (
            patch(
                "app.services.post.SocialAccountRepository.get_by_platform_for_user",
                new=AsyncMock(return_value=fake_social_account),
            ),
            patch(
                "app.services.post.publish_mastodon_status",
                new=publish_mock,
            ),
        ):
            async with AsyncSessionLocal() as db:
                db_post = await PostRepository.get_by_id(db, post.id)

                assert db_post is not None

                with pytest.raises(ScheduledPublishError) as exc_info:
                    await PostService.publish_scheduled_post(
                        db,
                        db_post,
                        test_user["id"],
                    )

                assert exc_info.value.retryable is True

            async with AsyncSessionLocal() as db:
                retry_post = await PostRepository.get_by_id(db, post.id)

                assert retry_post is not None
                assert retry_post.status == PostStatus.PUBLISHING.value

                result = await PostService.publish_scheduled_post(
                    db,
                    retry_post,
                    test_user["id"],
                )

                assert result.status == PostStatus.PUBLISHED.value
                assert result.external_post_id == "mastodon-status-retry-456"

        persisted = await get_post(post.id)

        assert persisted is not None
        assert persisted.status == PostStatus.PUBLISHED.value
        assert persisted.external_post_id == "mastodon-status-retry-456"
        assert persisted.publication_attempts == 2
        assert persisted.publication_key == (
            f"socialpilot:post:{post.id}:mastodon"
        )
        assert persisted.published_at is not None

        assert publish_mock.await_count == 2

    finally:
        await cleanup_post(post.id)