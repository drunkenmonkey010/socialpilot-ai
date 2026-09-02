from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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

    status: str = Field(
        default="draft",
        min_length=1,
        max_length=50,
    )

    scheduled_at: datetime | None = None

    published_at: datetime | None = None


class PostCreate(PostBase):
    """Fields required to create a post."""

    campaign_id: int = Field(
        ...,
        gt=0,
    )


class PostUpdate(BaseModel):
    """Fields that can be updated on a post."""

    content: str | None = Field(
        default=None,
        min_length=1,
    )

    platform: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    scheduled_at: datetime | None = None

    published_at: datetime | None = None


class PostResponse(PostBase):
    """API response for a post."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    campaign_id: int
    created_at: datetime
    updated_at: datetime