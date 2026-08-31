from fastapi import FastAPI

from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic AI social media management platform.",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return the current API health status."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.app_env,
    }