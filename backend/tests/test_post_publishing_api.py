from datetime import datetime, timezone

import pytest

from app.api.routes import post as post_routes
from app.models.post import PostStatus


async def create_brand(client, headers, name="Publishing Test Brand"):
    response = await client.post(
        "/brands",
        headers=headers,
        json={
            "name": name,
            "description": "Publishing API test brand",
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_campaign(
    client,
    headers,
    brand_id,
    name="Publishing Test Campaign",
):
    response = await client.post(
        "/campaigns",
        headers=headers,
        json={
            "brand_id": brand_id,
            "name": name,
            "description": "Publishing API test campaign",
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_post(
    client,
    headers,
    campaign_id,
    platform="mastodon",
):
    response = await client.post(
        "/posts",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "content": "Test post for publication.",
            "platform": platform,
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_test_post(client, headers):
    brand = await create_brand(client, headers)

    campaign = await create_campaign(
        client,
        headers,
        brand["id"],
    )

    return await create_post(
        client,
        headers,
        campaign["id"],
    )


async def approve_post(client, headers, post_id):
    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == PostStatus.PENDING_REVIEW.value

    response = await client.post(
        f"/posts/{post_id}/approve",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == PostStatus.APPROVED.value

    return response.json()


@pytest.mark.asyncio
async def test_publish_requires_authentication(client):
    """Publishing must require an authenticated user."""

    response = await client.post(
        "/posts/1/publish",
    )

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_draft_post_cannot_be_published(
    client,
    auth_headers,
):
    """A draft cannot bypass the Human-in-the-Loop approval boundary."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    assert post["status"] == PostStatus.DRAFT.value

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"
    assert "Only approved posts can be published" in data["error"]["message"]


@pytest.mark.asyncio
async def test_pending_review_post_cannot_be_published(
    client,
    auth_headers,
):
    """A post awaiting human review cannot be published."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    response = await client.post(
        f"/posts/{post['id']}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == PostStatus.PENDING_REVIEW.value

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_rejected_post_cannot_be_published(
    client,
    auth_headers,
):
    """A rejected post must be edited/resubmitted before publication."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    response = await client.post(
        f"/posts/{post['id']}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        f"/posts/{post['id']}/reject",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == PostStatus.REJECTED.value

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_approved_post_is_sent_to_publication_service(
    client,
    auth_headers,
    monkeypatch,
):
    """An approved post reaches the publication service."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    calls = []

    async def fake_publish(db, post_object, user_id):
        calls.append(
            {
                "post_id": post_object.id,
                "user_id": user_id,
                "status_before_publication": post_object.status,
            }
        )

        post_object.status = PostStatus.PUBLISHED.value

        return post_object

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == post["id"]
    assert data["status"] == PostStatus.PUBLISHED.value

    assert len(calls) == 1
    assert calls[0]["post_id"] == post["id"]
    assert calls[0]["user_id"] > 0
    assert calls[0]["status_before_publication"] == (
        PostStatus.PUBLISHING.value
    )


@pytest.mark.asyncio
async def test_successful_publish_returns_published_post(
    client,
    auth_headers,
    monkeypatch,
):
    """A successful publication is exposed as PUBLISHED through the API."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    async def fake_publish(db, post_object, user_id):
        post_object.status = PostStatus.PUBLISHED.value
        post_object.published_at = datetime.now(timezone.utc)

        return post_object

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == PostStatus.PUBLISHED.value
    assert data["published_at"] is not None


@pytest.mark.asyncio
async def test_publish_service_failure_returns_502(
    client,
    auth_headers,
    monkeypatch,
):
    """Unexpected publication failures are converted to a safe 502."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    async def fake_publish(db, post_object, user_id):
        raise RuntimeError(
            "External platform temporarily unavailable."
        )

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 502

    data = response.json()

    assert data["error"]["code"] == "BAD_GATEWAY"
    assert (
        data["error"]["message"]
        == "External platform temporarily unavailable."
    )


@pytest.mark.asyncio
async def test_publish_value_error_returns_409(
    client,
    auth_headers,
    monkeypatch,
):
    """Business-rule publication errors are returned as conflicts."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    async def fake_publish(db, post_object, user_id):
        raise ValueError(
            "Publication is not currently allowed."
        )

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"
    assert (
        data["error"]["message"]
        == "Publication is not currently allowed."
    )


@pytest.mark.asyncio
async def test_user_cannot_publish_another_users_post(
    client,
    auth_headers,
    second_auth_headers,
):
    """Publishing must enforce post ownership."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_nonexistent_post_cannot_be_published(
    client,
    auth_headers,
):
    """Publishing an unknown post returns 404."""

    response = await client.post(
        "/posts/999999999/publish",
        headers=auth_headers,
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_publishing_does_not_expose_social_credentials(
    client,
    auth_headers,
    monkeypatch,
):
    """Publication responses must never expose OAuth credentials."""

    post = await create_test_post(
        client,
        auth_headers,
    )

    await approve_post(
        client,
        auth_headers,
        post["id"],
    )

    async def fake_publish(db, post_object, user_id):
        post_object.status = PostStatus.PUBLISHED.value

        return post_object

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" not in data
    assert "refresh_token" not in data


@pytest.mark.asyncio
async def test_publish_endpoint_preserves_hitl_boundary(
    client,
    auth_headers,
    monkeypatch,
):
    """
    The API must not call the publication layer when approval
    has not occurred.

    PostService.publish_post() is intentionally left unmocked so
    that its APPROVED-state validation remains active.
    """

    post = await create_test_post(
        client,
        auth_headers,
    )

    assert post["status"] == PostStatus.DRAFT.value

    called = False

    async def fake_publish(db, post_object, user_id):
        nonlocal called
        called = True

        post_object.status = PostStatus.PUBLISHED.value

        return post_object

    monkeypatch.setattr(
        post_routes.PostService,
        "_publish_post",
        fake_publish,
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert called is False

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"
    assert "Only approved posts can be published" in data["error"]["message"]
