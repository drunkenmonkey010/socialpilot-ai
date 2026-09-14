import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.brand import router as brand_router
from app.api.routes.campaign import router as campaign_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.mastodon import router as mastodon_router
from app.api.routes.post import router as post_router
from app.api.routes.social_account import router as social_account_router
from app.api.routes.user import router as user_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.integrations.queue.redis import redis_queue


APP_VERSION = "0.1.0"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("socialpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""

    logger.info(
        "Starting %s version %s",
        settings.app_name,
        APP_VERSION,
    )

    yield

    logger.info(
        "Shutting down %s",
        settings.app_name,
    )


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    lifespan=lifespan,
)


allowed_origins = list(
    dict.fromkeys(
        [
            settings.frontend_url,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next,
):
    """Log every HTTP request and its response status."""

    logger.info(
        "%s %s",
        request.method,
        request.url.path,
    )

    response = await call_next(request)

    logger.info(
        "%s %s -> %s",
        request.method,
        request.url.path,
        response.status_code,
    )

    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    """Return a standardized validation error response."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    """Return a safe standardized response for unexpected errors."""

    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            }
        },
    )


@app.get("/health")
async def health():
    """Liveness endpoint."""

    return {
        "status": "healthy",
        "service": settings.app_name,
    }


@app.get("/ready")
async def ready():
    """Readiness endpoint checking database and Redis."""

    database_status = "ready"
    redis_status = "ready"

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"

    try:
        await redis_queue.ping()
    except Exception:
        redis_status = "unavailable"

    is_ready = (
        database_status == "ready"
        and redis_status == "ready"
    )

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.app_name,
        "checks": {
            "database": database_status,
            "redis": redis_status,
        },
    }

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if is_ready
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=payload,
    )


@app.get("/version")
async def version():
    """Return application version information."""

    return {
        "service": settings.app_name,
        "version": APP_VERSION,
    }


@app.get("/")
async def root():
    """Root application endpoint."""

    return {
        "name": settings.app_name,
        "version": APP_VERSION,
        "status": "running",
    }


app.include_router(auth_router)
app.include_router(brand_router)
app.include_router(campaign_router)
app.include_router(dashboard_router)
app.include_router(instagram_router)
app.include_router(mastodon_router)
app.include_router(post_router)
app.include_router(social_account_router)
app.include_router(user_router)