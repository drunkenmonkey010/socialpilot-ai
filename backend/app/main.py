"""
FastAPI application entry point.

This module creates the application instance and registers
all API routers.
"""

from fastapi import FastAPI

from app.api.routes.campaign import router as campaign_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic AI social media management platform.",
)


# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------

app.include_router(
    campaign_router,
    prefix="/api/v1",
)


# ---------------------------------------------------------------------------
# Health & Root Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return the current API health status."""

    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic API information."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }