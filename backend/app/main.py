import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.middleware import request_logging_middleware
from app.api.routes.auth import router as auth_router
from app.api.routes.brand import router as brand_router
from app.api.routes.campaign import router as campaign_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.mastodon import router as mastodon_router
from app.api.routes.post import router as post_router
from app.api.routes.social_account import router as social_account_router
from app.api.routes.user import router as user_router
from app.core.config import settings
from app.core.logging import configure_logging


configure_logging()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic AI social media management platform.",
)

app.state.logger = logging.getLogger("socialpilot.api")

app.middleware("http")(
    request_logging_middleware,
)


app.add_exception_handler(
    HTTPException,
    http_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    unhandled_exception_handler,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


app.include_router(auth_router)
app.include_router(brand_router)
app.include_router(campaign_router)
app.include_router(instagram_router)
app.include_router(mastodon_router)
app.include_router(post_router)
app.include_router(social_account_router)
app.include_router(user_router)
