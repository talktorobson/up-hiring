"""Configurações da aplicação carregadas via env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = Field(default="local")
    log_level: str = Field(default="INFO")

    # Database
    database_url: str = Field(default="postgresql+asyncpg://ats:ats@localhost:5432/ats")
    database_url_sync: str = Field(default="postgresql://ats:ats@localhost:5432/ats")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Clerk
    clerk_publishable_key: str = Field(default="")
    clerk_secret_key: str = Field(default="")
    clerk_webhook_secret: str = Field(default="")

    # S3
    s3_endpoint: str | None = Field(default=None)
    s3_access_key: str = Field(default="")
    s3_secret_key: str = Field(default="")
    s3_bucket: str = Field(default="up-hiring-dev")
    s3_region: str = Field(default="us-east-1")

    # Observability
    sentry_dsn: str | None = Field(default=None)
    logfire_token: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
