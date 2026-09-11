from datetime import datetime, timedelta, timezone

import pytest


async def create_brand(client, headers, name="Test Brand"):
    response = await client.post(
        "/brands",
        headers=headers,
        json={
            "name": name,
            "description": "Test brand description",
            "website_url": "https://example.com",
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_campaign(
    client,
    headers,
    brand_id,
    name="Test Campaign",
):
    response = await client.post(
        "/campaigns",
        headers=headers,
        json={
            "name": name,
            "description": "Test campaign description",
            "status": "draft",
            "brand_id": brand_id,
        },
    )

    assert response.status_code == 201

    return response.json()


async def create_post(
    client,
    headers,
    campaign_id,
    content="Test social media post",
    platform="mastodon",
):
    response = await client.post(
        "/posts",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "content": content,
            "platform": platform,
        },
    )

    assert response.status_code == 201

    return response.json()


@pytest.mark.asyncio
async def test_brand_crud(client, auth_headers):
    """A user can create, read, update, list, and delete their brand."""

    brand = await create_brand(client, auth_headers)

    brand_id = brand["id"]

    assert brand["name"] == "Test Brand"
    assert brand["description"] == "Test brand description"

    response = await client.get(
        f"/brands/{brand_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == brand_id

    response = await client.get(
        "/brands",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert any(item["id"] == brand_id for item in response.json())

    response = await client.patch(
        f"/brands/{brand_id}",
        headers=auth_headers,
        json={
            "name": "Updated Brand",
            "description": "Updated description",
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["name"] == "Updated Brand"
    assert updated["description"] == "Updated description"

    response = await client.delete(
        f"/brands/{brand_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    response = await client.get(
        f"/brands/{brand_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_brand_requires_authentication(client):
    """Brand endpoints require authentication."""

    response = await client.get("/brands")

    assert response.status_code == 401

    data = response.json()

    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_brand_cannot_be_accessed_by_another_user(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot access another user's brand."""

    brand = await create_brand(client, auth_headers)

    brand_id = brand["id"]

    response = await client.get(
        f"/brands/{brand_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/brands/{brand_id}",
        headers=second_auth_headers,
        json={"name": "Unauthorized Update"},
    )

    assert response.status_code == 404

    response = await client.delete(
        f"/brands/{brand_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_campaign_crud(client, auth_headers):
    """A user can create, read, update, list, and delete campaigns."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    campaign_id = campaign["id"]

    assert campaign["brand_id"] == brand["id"]
    assert campaign["name"] == "Test Campaign"
    assert campaign["status"] == "draft"

    response = await client.get(
        f"/campaigns/{campaign_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == campaign_id

    response = await client.get(
        f"/campaigns/brand/{brand['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    campaigns = response.json()

    assert any(item["id"] == campaign_id for item in campaigns)

    response = await client.patch(
        f"/campaigns/{campaign_id}",
        headers=auth_headers,
        json={
            "name": "Updated Campaign",
            "description": "Updated campaign description",
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["name"] == "Updated Campaign"
    assert updated["description"] == "Updated campaign description"

    response = await client.delete(
        f"/campaigns/{campaign_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    response = await client.get(
        f"/campaigns/{campaign_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_campaign_cannot_be_created_under_another_users_brand(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot create a campaign under another user's brand."""

    brand = await create_brand(client, auth_headers)

    response = await client.post(
        "/campaigns",
        headers=second_auth_headers,
        json={
            "brand_id": brand["id"],
            "name": "Unauthorized Campaign",
            "description": "Should not be created",
            "status": "draft",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_campaign_cannot_be_accessed_by_another_user(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot access another user's campaign."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    campaign_id = campaign["id"]

    response = await client.get(
        f"/campaigns/{campaign_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/campaigns/{campaign_id}",
        headers=second_auth_headers,
        json={"name": "Unauthorized Update"},
    )

    assert response.status_code == 404

    response = await client.delete(
        f"/campaigns/{campaign_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_creation_starts_as_draft(client, auth_headers):
    """Every newly created post must start in DRAFT."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    assert post["status"] == "draft"
    assert post["campaign_id"] == campaign["id"]
    assert post["platform"] == "mastodon"


@pytest.mark.asyncio
async def test_post_can_be_retrieved_and_listed_by_campaign(
    client,
    auth_headers,
):
    """A user can retrieve a post and list posts under its campaign."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.get(
        f"/posts/{post_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == post_id

    response = await client.get(
        f"/posts/campaign/{campaign['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    posts = response.json()

    assert any(item["id"] == post_id for item in posts)


@pytest.mark.asyncio
async def test_post_cannot_be_accessed_by_another_user(
    client,
    auth_headers,
    second_auth_headers,
):
    """A user cannot access another user's post."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.get(
        f"/posts/{post_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404

    response = await client.patch(
        f"/posts/{post_id}",
        headers=second_auth_headers,
        json={"content": "Unauthorized modification"},
    )

    assert response.status_code == 404

    response = await client.delete(
        f"/posts/{post_id}",
        headers=second_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_hitl_lifecycle_approval_path(
    client,
    auth_headers,
):
    """
    A post must pass through human review before scheduling.

    DRAFT -> PENDING_REVIEW -> APPROVED -> SCHEDULED
    """

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"

    response = await client.post(
        f"/posts/{post_id}/approve",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    ).isoformat()

    response = await client.post(
        f"/posts/{post_id}/schedule",
        headers=auth_headers,
        json={
            "scheduled_at": scheduled_at,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "scheduled"
    assert data["scheduled_at"] is not None


@pytest.mark.asyncio
async def test_post_hitl_rejection_path(
    client,
    auth_headers,
):
    """A post can be rejected and subsequently resubmitted for review."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"

    response = await client.post(
        f"/posts/{post_id}/reject",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_post_cannot_be_approved_without_review(
    client,
    auth_headers,
):
    """A draft cannot bypass the human review boundary."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    response = await client.post(
        f"/posts/{post['id']}/approve",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_post_cannot_be_scheduled_before_approval(
    client,
    auth_headers,
):
    """A draft cannot be scheduled without human approval."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    ).isoformat()

    response = await client.post(
        f"/posts/{post['id']}/schedule",
        headers=auth_headers,
        json={
            "scheduled_at": scheduled_at,
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_post_cannot_be_published_before_approval(
    client,
    auth_headers,
):
    """Publishing is blocked until human approval occurs."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    response = await client.post(
        f"/posts/{post['id']}/publish",
        headers=auth_headers,
    )

    assert response.status_code == 409

    data = response.json()

    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_post_cannot_be_rejected_without_review(
    client,
    auth_headers,
):
    """A draft cannot be rejected before entering human review."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    response = await client.post(
        f"/posts/{post['id']}/reject",
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_post_cannot_be_submitted_for_review_twice(
    client,
    auth_headers,
):
    """A post already awaiting review cannot be submitted again."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_post_cannot_be_edited_after_approval(
    client,
    auth_headers,
):
    """Approved posts are no longer editable."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    response = await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.post(
        f"/posts/{post_id}/approve",
        headers=auth_headers,
    )

    assert response.status_code == 200

    response = await client.patch(
        f"/posts/{post_id}",
        headers=auth_headers,
        json={
            "content": "This modification should be rejected",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rejected_post_can_be_edited(
    client,
    auth_headers,
):
    """Rejected posts remain editable before resubmission."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    response = await client.post(
        f"/posts/{post_id}/reject",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    response = await client.patch(
        f"/posts/{post_id}",
        headers=auth_headers,
        json={
            "content": "Improved content after rejection",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Improved content after rejection"


@pytest.mark.asyncio
async def test_schedule_rejects_past_time(
    client,
    auth_headers,
):
    """Approved posts cannot be scheduled in the past."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    post = await create_post(
        client,
        auth_headers,
        campaign["id"],
    )

    post_id = post["id"]

    await client.post(
        f"/posts/{post_id}/submit-review",
        headers=auth_headers,
    )

    await client.post(
        f"/posts/{post_id}/approve",
        headers=auth_headers,
    )

    past_time = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()

    response = await client.post(
        f"/posts/{post_id}/schedule",
        headers=auth_headers,
        json={
            "scheduled_at": past_time,
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_generate_post_creates_draft(
    client,
    auth_headers,
):
    """
    AI-generated content must enter the HITL workflow as DRAFT.

    AI generation cannot directly create an approved post.
    """

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    response = await client.post(
        f"/campaigns/{campaign['id']}/generate-post",
        headers=auth_headers,
        params={
            "platform": "mastodon",
        },
    )

    assert response.status_code == 201

    post = response.json()

    assert post["campaign_id"] == campaign["id"]
    assert post["platform"] == "mastodon"
    assert post["status"] == "draft"
    assert post["content"]


@pytest.mark.asyncio
async def test_generate_post_cannot_be_requested_for_another_users_campaign(
    client,
    auth_headers,
    second_auth_headers,
):
    """AI generation cannot bypass campaign ownership."""

    brand = await create_brand(client, auth_headers)

    campaign = await create_campaign(
        client,
        auth_headers,
        brand["id"],
    )

    response = await client.post(
        f"/campaigns/{campaign['id']}/generate-post",
        headers=second_auth_headers,
        params={
            "platform": "mastodon",
        },
    )

    assert response.status_code == 404
