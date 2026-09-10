import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.brand import Brand
from app.models.campaign import Campaign
from app.models.post import Post, PostStatus
from app.models.user import User
from app.services.post import PostService
from app.worker.recovery import recover_jobs


class FakeReconcilablePublisher:
    platform = "fake_reconcile"

    def __init__(self):
        self.publish_calls = 0
        self.reconcile_calls = 0

    async def reconcile(
        self,
        account,
        content,
        publication_key,
    ):
        from app.integrations.platforms.types import ReconciliationResult

        self.reconcile_calls += 1

        return ReconciliationResult(
            found=True,
            external_post_id="external-recovered-456",
            metadata={
                "source": "fake-reconciliation",
                "publication_key": publication_key,
            },
        )

    async def publish(
        self,
        account,
        content,
        publication_key=None,
    ):
        self.publish_calls += 1

        raise AssertionError(
            "publish() must NOT be called when reconciliation succeeds."
        )


async def _create_publishing_post(db):
    unique_id = uuid.uuid4().hex

    user = User(
        email=f"recovery-test-{unique_id}@example.com",
        password_hash=hash_password("test-password"),
    )
    db.add(user)
    await db.flush()

    brand = Brand(
        name=f"Recovery Test Brand {unique_id}",
        user_id=user.id,
    )
    db.add(brand)
    await db.flush()

    campaign = Campaign(
        name=f"Recovery Test Campaign {unique_id}",
        brand_id=brand.id,
    )
    db.add(campaign)
    await db.flush()

    post = Post(
        campaign_id=campaign.id,
        content="Recovery reconciliation test post",
        platform="fake_reconcile",
        status=PostStatus.PUBLISHING.value,
        publication_key=f"socialpilot:recovery:test:{unique_id}",
        publication_attempts=1,
    )

    db.add(post)
    await db.commit()
    await db.refresh(post)

    return post, user.id


@pytest.mark.asyncio
async def test_recovery_reconciles_missing_redis_job_without_republishing():
    """
    Critical crash-consistency scenario:

        External publication succeeded
        -> DB still says PUBLISHING
        -> Redis job disappeared
        -> recovery runs
        -> reconciliation finds the external post
        -> DB becomes PUBLISHED
        -> publish() is never called again.
    """

    publisher = FakeReconcilablePublisher()

    fake_account = object()

    async with AsyncSessionLocal() as db:
        post, user_id = await _create_publishing_post(db)

    try:
        with patch(
            "app.services.publication.PublicationService.get_publisher",
            return_value=publisher,
        ), patch(
            "app.services.publication.PublicationService.get_social_account",
            new=AsyncMock(return_value=fake_account),
        ), patch(
            "app.worker.recovery.PostRepository.get_publishing_posts",
            new=AsyncMock(
                return_value=[(post, user_id)]
            ),
        ), patch(
            "app.worker.recovery.redis_queue.has_scheduled_post_job",
            new=AsyncMock(return_value=False),
        ), patch(
            "app.worker.recovery.redis_queue.enqueue_scheduled_post",
            new=AsyncMock(),
        ):
            await recover_jobs()

        async with AsyncSessionLocal() as db:
            refreshed_post = await PostService.get_post(
                db,
                post.id,
                user_id,
            )

            assert refreshed_post is not None
            assert refreshed_post.status == PostStatus.PUBLISHED.value
            assert (
                refreshed_post.external_post_id
                == "external-recovered-456"
            )

        assert publisher.reconcile_calls == 1
        assert publisher.publish_calls == 0

    finally:
        async with AsyncSessionLocal() as db:
            refreshed_post = await PostService.get_post(
                db,
                post.id,
                user_id,
            )

            if refreshed_post is not None:
                await db.delete(refreshed_post)
                await db.commit()