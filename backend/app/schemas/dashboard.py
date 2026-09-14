from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardUser(BaseModel):
    """Authenticated user information displayed by the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DashboardWorkspace(BaseModel):
    """Workspace summary for the dashboard."""

    name: str
    brand_count: int


class DashboardStats(BaseModel):
    """Post counts used by the dashboard overview."""

    drafts: int
    needs_review: int
    scheduled: int
    published: int


class DashboardUpcomingPost(BaseModel):
    """A scheduled post displayed in the upcoming-content panel."""

    id: int
    content: str
    platform: str
    scheduled_at: datetime
    campaign_name: str


class DashboardReviewPost(BaseModel):
    """A post waiting for human approval."""

    id: int
    content: str
    platform: str
    created_at: datetime
    campaign_name: str


class DashboardOverviewResponse(BaseModel):
    """Complete authenticated dashboard overview."""

    user: DashboardUser
    workspace: DashboardWorkspace
    stats: DashboardStats
    upcoming: list[DashboardUpcomingPost]
    needs_review: list[DashboardReviewPost]
    connected_accounts: int