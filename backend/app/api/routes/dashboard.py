from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard import DashboardService


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardOverviewResponse:
    """
    Return the complete dashboard overview for the authenticated user.

    The response aggregates the user's:
    - workspace information
    - post statistics
    - upcoming scheduled content
    - posts awaiting human review
    - connected social accounts
    """

    return await DashboardService.get_overview(
        db,
        current_user,
    )