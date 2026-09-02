from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BrandBase(BaseModel):
    name: str
    description: str | None = None
    website_url: str | None = None


class BrandCreate(BrandBase):
    user_id: int


class BrandUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website_url: str | None = None


class BrandResponse(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime