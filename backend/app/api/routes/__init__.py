from app.api.routes.brand import router as brand_router
from app.api.routes.campaign import router as campaign_router
from app.api.routes.user import router as user_router


__all__ = [
    "brand_router",
    "campaign_router",
    "user_router",
]