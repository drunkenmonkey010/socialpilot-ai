from datetime import datetime, timezone

import pytest

from app.core.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.models.publication import PublicationStatus
from app.models.social_account import SocialAccount
from app.repositories.post import PostRepository
from app.repositories.publication import PublicationRepository
from app.services.publication import PublicationService


async def create_publication_test_data(
    user_id: int,
):
    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=user_id,
            name=f"Publication Test Brand {datetime.now(timezone.utc).timestamp()}",
            description="Publication persistence test",
        )
        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name=f"Publication Test Campaign {datetime.now(timezone.utc).timestamp()}",
            description="Publication persistence test",
        )
        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Publication persistence test post",
            platform="mastodon",
            status=PostStatus.PUBLISHING.value,
        )
        db.add(post)
        await db.flush()

        account = SocialAccount(
            user_id=user_id,
            platform="mastodon",
            account_name="Publication Test Account",
            account_id=f"publication-test-{post.id}",
            access_token="test-token",
            is_active=True,
        )
        db.add(account)

        await db.commit()

        await db.refresh(post)
        await db.refresh(account)

        return post, account, campaign.id, brand.id


async def cleanup_publication_test_data(
    post_id: int,
    account_id: int,
    campaign_id: int,
    brand_id: int,
):
    async with AsyncSessionLocal() as db:
        publication = (
            await PublicationRepository.get_by_post_and_account(
                db,
                post_id,
                account_id,
            )
        )

        if publication is not None:
            await db.delete(publication)
            await db.flush()

        post = await PostRepository.get_by_id(
            db,
            post_id,
        )

        if post is not None:
            await db.delete(post)
            await db.flush()

        campaign = await db.get(
            Campaign,
            campaign_id,
        )

        if campaign is not None:
            await db.delete(campaign)
            await db.flush()

        brand = await db.get(
            Brand,
            brand_id,
        )

        if brand is not None:
            await db.delete(brand)
            await db.flush()

        account = await db.get(
            SocialAccount,
            account_id,
        )

        if account is not None:
            await db.delete(account)
            await db.flush()

        await db.commit()


@pytest.mark.asyncio
async def test_get_or_create_publication_creates_durable_record(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            publication = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert publication is not None
            assert publication.id is not None
            assert publication.post_id == post.id
            assert publication.social_account_id == account.id
            assert publication.platform == "mastodon"
            assert publication.status == (
                PublicationStatus.PENDING.value
            )
            assert publication.attempt_count == 0
            assert publication.external_post_id is None
            assert publication.publication_key == (
                f"socialpilot:post:{post.id}:account:{account.id}"
            )

        async with AsyncSessionLocal() as db:
            persisted = (
                await PublicationRepository.get_by_post_and_account(
                    db,
                    post.id,
                    account.id,
                )
            )

            assert persisted is not None
            assert persisted.id == publication.id

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )


@pytest.mark.asyncio
async def test_get_or_create_publication_is_idempotent(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            first = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            second = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert first is not None
            assert second is not None
            assert first.id == second.id

            publications = (
                await PublicationRepository.get_by_post(
                    db,
                    post.id,
                )
            )

            assert len(publications) == 1

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )


@pytest.mark.asyncio
async def test_publication_attempt_is_persisted(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            publication = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert publication is not None

            updated = await PublicationRepository.increment_attempt(
                db,
                publication.id,
            )

            assert updated is not None
            assert updated.attempt_count == 1
            assert updated.status == (
                PublicationStatus.PUBLISHING.value
            )
            assert updated.first_attempt_at is not None
            assert updated.last_attempt_at is not None

        async with AsyncSessionLocal() as db:
            persisted = await PublicationRepository.get_by_id(
                db,
                publication.id,
            )

            assert persisted is not None
            assert persisted.attempt_count == 1
            assert persisted.status == (
                PublicationStatus.PUBLISHING.value
            )

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )


@pytest.mark.asyncio
async def test_publication_success_is_persisted(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            publication = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert publication is not None

            await PublicationRepository.increment_attempt(
                db,
                publication.id,
            )

            updated = await PublicationRepository.mark_published(
                db,
                publication.id,
                "external-publication-123",
                {
                    "source": "test",
                },
            )

            assert updated is not None
            assert updated.status == (
                PublicationStatus.PUBLISHED.value
            )
            assert updated.external_post_id == (
                "external-publication-123"
            )
            assert updated.published_at is not None
            assert updated.publication_metadata == {
                "source": "test",
            }
            assert updated.last_error is None

        async with AsyncSessionLocal() as db:
            persisted = await PublicationRepository.get_by_id(
                db,
                publication.id,
            )

            assert persisted is not None
            assert persisted.status == (
                PublicationStatus.PUBLISHED.value
            )
            assert persisted.external_post_id == (
                "external-publication-123"
            )

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )


@pytest.mark.asyncio
async def test_publication_error_is_persisted(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            publication = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert publication is not None

            await PublicationRepository.increment_attempt(
                db,
                publication.id,
            )

            updated = await PublicationRepository.record_error(
                db,
                publication.id,
                "temporary platform failure",
                60,
            )

            assert updated is not None
            assert updated.status == (
                PublicationStatus.PUBLISHING.value
            )
            assert updated.last_error == (
                "temporary platform failure"
            )
            assert updated.retry_after_seconds == 60

        async with AsyncSessionLocal() as db:
            persisted = await PublicationRepository.get_by_id(
                db,
                publication.id,
            )

            assert persisted is not None
            assert persisted.last_error == (
                "temporary platform failure"
            )
            assert persisted.retry_after_seconds == 60

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )


@pytest.mark.asyncio
async def test_publication_permanent_failure_is_persisted(
    test_user,
):
    post, account, campaign_id, brand_id = (
        await create_publication_test_data(
            test_user["id"],
        )
    )

    try:
        async with AsyncSessionLocal() as db:
            publication = (
                await PublicationService.get_or_create_publication(
                    db,
                    post,
                    account,
                )
            )

            assert publication is not None

            await PublicationRepository.increment_attempt(
                db,
                publication.id,
            )

            updated = await PublicationRepository.mark_failed(
                db,
                publication.id,
                "invalid authentication",
            )

            assert updated is not None
            assert updated.status == (
                PublicationStatus.FAILED.value
            )
            assert updated.last_error == (
                "invalid authentication"
            )
            assert updated.external_post_id is None

    finally:
        await cleanup_publication_test_data(
            post.id,
            account.id,
            campaign_id,
            brand_id,
        )