"""Application settings, loaded from environment variables / .env (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_key: str = "change-me-dev-key"
    rate_limit_per_minute: int = 60
    auto_bootstrap: bool = True

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/shoppilot"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["rules", "openai", "ollama"] = "rules"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"
    llm_timeout_seconds: float = 20.0

    embedding_provider: Literal["hash", "sentence-transformers"] = "hash"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    return_window_days: int = 30
    cache_ttl_seconds: int = 60
    rag_min_score: float = 0.12


@lru_cache
def get_settings() -> Settings:
    return Settings()
