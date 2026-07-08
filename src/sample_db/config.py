"""Application settings loaded from the environment and .env file."""

from dataclasses import dataclass
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the SQL agent."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr
    model: str = "gpt-5.4-mini"
    pg_app_dsn: str
    pg_auth_dsn: str
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()  # ty:ignore[missing-argument]


@dataclass(frozen=True)
class PromptConfig:
    """Template variables for the agent prompt templates."""

    dialect: str = "PostgreSQL"
    top_k: int = 5


@lru_cache
def get_config() -> PromptConfig:
    """Return the cached prompt template configuration."""
    return PromptConfig()
