"""Application configuration loaded from environment variables via pydantic-settings."""

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configurable application settings.

    Values are loaded in priority order:
    1. Environment variables
    2. .env file (if present)
    3. Field defaults
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/stashboard"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── OAuth (Google) ────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: List[str] = [
        "chrome-extension://",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # ── Misc ──────────────────────────────────────────────────────────────────
    debug: bool = False
    app_name: str = "Stashboard"
    app_version: str = "0.1.0"

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def default_celery_broker(cls, v: str, info) -> str:
        """Fall back to redis_url if celery_broker_url is not set."""
        if not v:
            return info.data.get("redis_url", "redis://localhost:6379/0")
        return v

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def default_celery_backend(cls, v: str, info) -> str:
        """Fall back to redis_url if celery_result_backend is not set."""
        if not v:
            return info.data.get("redis_url", "redis://localhost:6379/0")
        return v


@lru_cache
def get_settings() -> Settings:
    """Returns a cached singleton Settings instance."""
    return Settings()


settings = get_settings()
