"""
Centralized application configuration.

All secrets and environment-dependent values are read from environment
variables via pydantic-settings. Nothing here is hardcoded so the same
image can run in dev, CI, or production simply by changing the .env file.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Integration Hub"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # --- Security / JWT ---
    JWT_SECRET_KEY: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+psycopg2://integration_hub:integration_hub@db:5432/integration_hub"
    )

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- GitHub integration ---
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/integrations/github/callback"

    # --- Slack integration ---
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/integrations/slack/callback"

    # --- Rate limiting (basic, in-memory / redis token bucket) ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Credential encryption at rest ---
    # A Fernet key (32 url-safe base64-encoded bytes). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    INTEGRATION_ENCRYPTION_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
