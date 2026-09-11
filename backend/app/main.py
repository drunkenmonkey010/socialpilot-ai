import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

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
from app.core.database import engine
from app.core.logging import configure_logging
from app.integrations.queue.redis import redis_queue


configure_logging()

APP_VERSION = "0.1.0"


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
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
    """
    Liveness endpoint.

    Confirms that the application process is running.
    Dependency availability is checked by /ready.
    """

    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get(
    "/ready",
    response_model=None,
)
async def readiness_check() -> dict | JSONResponse:
    """
    Readiness endpoint.

    Confirms that the application can reach its
    required PostgreSQL and Redis dependencies.
    """

    checks: dict[str, str] = {}

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        checks["database"] = "ready"

    except Exception:
        checks["database"] = "unavailable"

    try:
        redis_ready = await redis_queue.ping()

        checks["redis"] = (
            "ready"
            if redis_ready
            else "unavailable"
        )

    except Exception:
        checks["redis"] = "unavailable"

    all_ready = all(
        status == "ready"
        for status in checks.values()
    )

    payload = {
        "status": "ready" if all_ready else "not_ready",
        "service": settings.app_name,
        "checks": checks,
    }

    if not all_ready:
        return JSONResponse(
            status_code=503,
            content=payload,
        )

    return payload


@app.get("/version")
async def version_check() -> dict[str, str]:
    """Return the running application version."""

    return {
        "service": settings.app_name,
        "version": APP_VERSION,
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": APP_VERSION,
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
