import uuid

import pytest

from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.repositories.post import PostRepository
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_get_by_publication_key(test_user):
    publication_key = f"test-{uuid.uuid4().hex}"

    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=test_user["id"],
            name=f"Test Brand {uuid.uuid4().hex[:8]}",
            description="Repository test brand",
        )
        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name=f"Test Campaign {uuid.uuid4().hex[:8]}",
            description="Repository test campaign",
        )
        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Repository idempotency test",
            platform="mastodon",
            status=PostStatus.DRAFT.value,
            publication_key=publication_key,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        found = await PostRepository.get_by_publication_key(
            db,
            publication_key,
        )

        assert found is not None
        assert found.id == post.id
        assert found.publication_key == publication_key

        await db.delete(post)
        await db.delete(campaign)
        await db.delete(brand)
        await db.commit()


@pytest.mark.asyncio
async def test_increment_publication_attempts(test_user):
    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=test_user["id"],
            name=f"Test Brand {uuid.uuid4().hex[:8]}",
            description="Repository test brand",
        )
        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name=f"Test Campaign {uuid.uuid4().hex[:8]}",
            description="Repository test campaign",
        )
        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Attempt counter test",
            platform="mastodon",
            status=PostStatus.PUBLISHING.value,
            publication_attempts=0,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        first_attempt = await PostRepository.increment_publication_attempts(
            db,
            post.id,
        )

        assert first_attempt == 1

        second_attempt = await PostRepository.increment_publication_attempts(
            db,
            post.id,
        )

        assert second_attempt == 2

        await db.delete(post)
        await db.delete(campaign)
        await db.delete(brand)
        await db.commit()


@pytest.mark.asyncio
async def test_record_publication_result(test_user):
    external_post_id = f"mastodon-{uuid.uuid4().hex}"

    async with AsyncSessionLocal() as db:
        brand = Brand(
            user_id=test_user["id"],
            name=f"Test Brand {uuid.uuid4().hex[:8]}",
            description="Repository test brand",
        )
        db.add(brand)
        await db.flush()

        campaign = Campaign(
            brand_id=brand.id,
            name=f"Test Campaign {uuid.uuid4().hex[:8]}",
            description="Repository test campaign",
        )
        db.add(campaign)
        await db.flush()

        post = Post(
            campaign_id=campaign.id,
            content="Publication result test",
            platform="mastodon",
            status=PostStatus.PUBLISHING.value,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        updated = await PostRepository.record_publication_result(
            db,
            post.id,
            external_post_id,
        )

        assert updated is not None
        assert updated.external_post_id == external_post_id
        assert updated.status == PostStatus.PUBLISHED.value
        assert updated.published_at is not None

        await db.delete(post)
        await db.delete(campaign)
        await db.delete(brand)
        await db.commit()