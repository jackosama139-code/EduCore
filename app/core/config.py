"""Central configuration. Every secret comes from environment variables / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "EduCore"
    API_PREFIX: str = "/api/v1"

    # No defaults for secrets: the app refuses to start without them.
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ATTENDANCE_THRESHOLD: float = 75.0

    # Optional AI module
    AI_ENABLED: bool = False
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "claude-sonnet-5-5"
    MAX_UPLOAD_MB: int = 10

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_must_be_long(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
