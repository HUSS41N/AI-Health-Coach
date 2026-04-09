from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-haiku-20241022"

    short_term_message_limit: int = 15
    summary_every_n_user_messages: int = 10
    memory_context_message_limit: int = 10
    memory_cache_ttl_seconds: int = 420
    episodic_memory_limit: int = 5
    max_user_message_chars: int = 8000
    llm_timeout_seconds: float = 60.0
    rate_limit_per_minute: int = 40
    llm_cache_ttl_seconds: int = 300
    default_user_id: str = "default"

    # Guardrails (see guardrails/)
    guardrail_max_message_chars: int = 2000
    guardrail_rate_limit_per_minute: int = 10
    guardrail_json_retries: int = 2

    @field_validator("database_url")
    @classmethod
    def strip_database_url(cls, v: str) -> str:
        return v.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
