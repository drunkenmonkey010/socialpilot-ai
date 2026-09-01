"""
Pydantic schemas for campaign API operations.

These schemas define the data contract between the API layer
and clients consuming the SocialPilot AI backend.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignBase(BaseModel):
    """Shared fields for campaign requests and responses."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="draft", max_length=50)


class CampaignCreate(CampaignBase):
    """Schema used when creating a new campaign."""

    brand_id: int = Field(..., gt=0)


class CampaignUpdate(BaseModel):
    """Schema used when updating an existing campaign."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)


class CampaignResponse(CampaignBase):
    """Schema returned by the API for a campaign."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    created_at: datetime
    updated_at: datetime