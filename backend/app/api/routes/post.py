"""
Post API routes.

HTTP-specific concerns live here. Business logic is delegated to
PostService, which uses PostRepository for persistence.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.post import (
    PostCreate,
    PostResponse,
    PostUpdate,
)
from app.services.post import PostService


router = APIRouter(
    prefix="/posts",
    tags=["Posts"],
)


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a post under a campaign owned by the current user."""

    post = await PostService.create_post(
        db,
        current_user.id,
        post_data,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return post


@router.get(
    "/{post_id}",
    response_model=PostResponse,
)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Return a post owned by the current user."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return post


@router.get(
    "/campaign/{campaign_id}",
    response_model=list[PostResponse],
)
async def get_campaign_posts(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PostResponse]:
    """Return posts belonging to a campaign owned by the current user."""

    posts = await PostService.get_campaign_posts(
        db,
        campaign_id,
        current_user.id,
    )

    if posts is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    return posts


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
)
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Update a post only if the user owns its campaign."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.update_post(
            db,
            post,
            post_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{post_id}/submit-review",
    response_model=PostResponse,
)
async def submit_post_for_review(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Submit a draft or rejected post for human review."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.submit_for_review(
            db,
            post,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{post_id}/approve",
    response_model=PostResponse,
)
async def approve_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """
    Approve a post after human review.

    This endpoint represents the human-in-the-loop approval boundary.
    """

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.approve_post(
            db,
            post,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{post_id}/reject",
    response_model=PostResponse,
)
async def reject_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Reject a post during human review."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.reject_post(
            db,
            post,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{post_id}/schedule",
    response_model=PostResponse,
)
async def schedule_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Schedule an approved post for future publication."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.schedule_post(
            db,
            post,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{post_id}/publish",
    response_model=PostResponse,
)
async def publish_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """
    Publish an approved post to its connected social platform.

    Publishing is intentionally restricted to APPROVED posts.
    This prevents drafts or posts awaiting human review from
    reaching the external platform.
    """

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    try:
        return await PostService.publish_post(
            db,
            post,
            current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a post only if the user owns its campaign."""

    post = await PostService.get_post(
        db,
        post_id,
        current_user.id,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    await PostService.delete_post(
        db,
        post,
    )