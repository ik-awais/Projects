# backend/app/core/config.py

"""
Application configuration, loaded from environment variables.
Single source of truth for all settings — no other module should call
os.environ or os.getenv directly.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────
    APP_NAME: str = "NovaMind"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        ...,
        description="Async SQLAlchemy connection string, e.g. "
        "postgresql+asyncpg://user:pass@host:5432/dbname",
    )
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)
    DATABASE_ECHO: bool = Field(default=False)

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ── JWT / security ────────────────────────────────────────────────
    JWT_SECRET: str = Field(..., min_length=32)
    ENCRYPTION_KEY: str = Field(..., min_length=32)

    # ── NVIDIA NIM ────────────────────────────────────────────────────
    NVIDIA_API_KEY_1: str = Field(..., description="Primary NVIDIA NIM API key")
    NVIDIA_API_KEY_2: str = Field(..., description="Secondary NVIDIA NIM API key (failover)")

    # ── Search providers ──────────────────────────────────────────────
    TAVILY_API_KEY: str = Field(..., description="Tavily search API key")
    BRAVE_API_KEY: str = Field(..., description="Brave search API key")

    # ── SMTP (email verification / password reset) ───────────────────
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM_EMAIL: str = Field(default="noreply@novamind.local")
    SMTP_USE_TLS: bool = Field(default=True)

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ── Frontend URL (used in verification/reset emails) ─────────────
    FRONTEND_BASE_URL: str = Field(default="http://localhost:3000")

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"development", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}, got '{value}'")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the 'postgresql+asyncpg://' scheme for async SQLAlchemy."
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance. pydantic-settings raises a clear
    validation error at first call if any required env var is missing,
    which fails the app fast at startup rather than at first use.
    """
    return Settings()


settings = get_settings()