from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SocialAccountBase(BaseModel):
    platform: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    account_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    access_token: str = Field(
        ...,
        min_length=1,
    )

    refresh_token: str | None = None

    token_expires_at: datetime | None = None

    is_active: bool = True


class SocialAccountCreate(SocialAccountBase):
    """Fields required when creating a social account internally."""

    pass


class SocialAccountUpdate(BaseModel):
    """Fields that can be updated on a social account."""

    platform: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    account_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    account_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    access_token: str | None = Field(
        default=None,
        min_length=1,
    )

    refresh_token: str | None = None

    token_expires_at: datetime | None = None

    is_active: bool | None = None


class SocialAccountResponse(BaseModel):
    """
    Safe API response for a connected social account.

    OAuth credentials are intentionally excluded.
    Access tokens and refresh tokens must remain backend-only.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    user_id: int

    platform: str

    account_name: str

    account_id: str

    token_expires_at: datetime | None

    is_active: bool

    created_at: datetime

    updated_at: datetime