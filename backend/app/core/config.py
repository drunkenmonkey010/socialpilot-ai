from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root:
# socialpilot-ai/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ============================================================
    # Application
    # ============================================================

    app_name: str = "SocialPilot AI"
    app_env: str = "development"
    debug: bool = True

    # ============================================================
    # Backend
    # ============================================================

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # ============================================================
    # Database
    # ============================================================

    database_url: str = (
        "postgresql+asyncpg://socialpilot:password@localhost:5433/socialpilot"
    )

    # ============================================================
    # Redis
    # ============================================================

    redis_url: str = "redis://localhost:6379/0"

    # ============================================================
    # Authentication
    # ============================================================

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # ============================================================
    # Token Encryption
    # ============================================================

    token_encryption_key: str

    # ============================================================
    # LLM
    # ============================================================

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    openai_api_key: str | None = None

    # ============================================================
    # Frontend / Backend URLs
    # ============================================================

    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # ============================================================
    # Instagram
    # ============================================================

    instagram_app_id: str | None = None
    instagram_app_secret: str | None = None

    instagram_redirect_uri: str = (
        "http://localhost:8000/social-accounts/instagram/callback"
    )

    instagram_api_base_url: str = (
        "https://graph.instagram.com/v24.0"
    )

    instagram_access_token: str | None = None

    # ============================================================
    # Mastodon
    # ============================================================

    mastodon_instance_url: str = "https://mastodon.social"
    mastodon_client_id: str | None = None
    mastodon_client_secret: str | None = None

    mastodon_redirect_uri: str = (
        "http://localhost:8000/social-accounts/mastodon/callback"
    )

    # ============================================================
    # Validation
    # ============================================================

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """Reject missing or weak JWT signing secrets."""

        if not value or not value.strip():
            raise ValueError("JWT_SECRET must be configured.")

        if len(value) < 32:
            raise ValueError(
                "JWT_SECRET must contain at least 32 characters."
            )

        if value == "development-only-secret":
            raise ValueError(
                "The development-only JWT secret cannot be used."
            )

        return value

    @field_validator("token_encryption_key")
    @classmethod
    def validate_token_encryption_key(cls, value: str) -> str:
        """Validate the Fernet encryption key."""

        if not value or not value.strip():
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY must be configured."
            )

        return value

    # ============================================================
    # Pydantic Settings configuration
    # ============================================================

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