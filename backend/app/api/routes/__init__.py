from app.api.routes.auth import router as auth_router
from app.api.routes.brand import router as brand_router
from app.api.routes.campaign import router as campaign_router
from app.api.routes.post import router as post_router
from app.api.routes.user import router as user_router


__all__ = [
    "auth_router",
    "brand_router",
    "campaign_router",
    "post_router",
    "user_router",
]