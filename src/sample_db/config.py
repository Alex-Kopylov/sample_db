"""Application settings loaded from the environment and .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the SQL agent."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr
    model: str = "gpt-5.4-mini"
    db_path: Path = Path("data/app.db")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
