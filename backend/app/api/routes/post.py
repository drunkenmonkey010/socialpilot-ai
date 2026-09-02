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

    return await PostService.update_post(
        db,
        post,
        post_data,
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