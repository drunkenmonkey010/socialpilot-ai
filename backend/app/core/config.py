from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root:
# socialpilot-ai/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "SocialPilot AI"
    app_env: str = "development"
    debug: bool = True

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Database
    database_url: str = (
        "postgresql+asyncpg://socialpilot:password@localhost:5433/socialpilot"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Authentication
    jwt_secret: str = "development-only-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # LLM
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: str | None = None

    # Frontend / Backend URLs
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()


settings = get_settings()