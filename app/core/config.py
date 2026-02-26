"""
app/core/config.py
──────────────────
All runtime configuration is sourced from environment variables.
Never hardcode secrets. Use a .env file locally (see .env.example).
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── LLM Parameters (documented rationale) ────────────────────────────────
    # temperature=0.3  → low randomness for deterministic JSON; allows slight
    #                    creativity so test cases aren't robotically identical.
    # max_tokens=2048  → ~300-400 tokens per test case × 4 cases + overhead.
    #                    1024 was too tight for complex domains (payments, cart).
    # top_p=0.95       → nucleus sampling complement; keeps tail improbabilities out.
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT_SECONDS: int = 30

    # ── Validation ───────────────────────────────────────────────────────────
    MAX_RETRIES: int = 2
    MIN_TEST_CASES: int = 2
    MAX_TEST_CASES: int = 10
    EXPECTED_TEST_CASES: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
