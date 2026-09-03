from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.post import PostStatus


class PostBase(BaseModel):
    """Shared fields for social media posts."""

    content: str = Field(
        ...,
        min_length=1,
    )

    platform: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    scheduled_at: datetime | None = None


class PostCreate(PostBase):
    """Fields required to create a post."""

    campaign_id: int = Field(
        ...,
        gt=0,
    )


class PostUpdate(BaseModel):
    """Fields that can be edited while a post is in an editable state."""

    content: str | None = Field(
        default=None,
        min_length=1,
    )

    platform: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    scheduled_at: datetime | None = None


class PostResponse(BaseModel):
    """API response for a post."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    campaign_id: int
    content: str
    platform: str
    status: PostStatus
    scheduled_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime