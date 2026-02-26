"""
app/services/llm_client.py
──────────────────────────
Thin async wrapper around the OpenAI Chat Completions API.

Responsabilidades:
  • Send prompt, recibe raw text + stop_reason (stop | length | content_filter | …)
  • Muestra stop_reason para diagnóstico (considerar aumentar max_tokens o revisar heurística de reparación)
  • Handle timeouts, network errors, HTTP errors consistently
  • parsing, scoring – single responsibility
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.prompts import SYSTEM_PROMPT, build_user_message
from app.utils.logger import get_logger

logger = get_logger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


@dataclass
class LLMResponse:
    text: str
    stop_reason: str   # "stop" | "length" | "content_filter" | …
    model: str


class LLMClient:
    """Async OpenAI client. Instantiate once (e.g. as a dependency)."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.LLM_TIMEOUT_SECONDS),
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    async def generate(self, user_story: str) -> LLMResponse:
        payload = {
            "model": settings.OPENAI_MODEL,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "top_p": settings.LLM_TOP_P,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(user_story)},
            ],
        }

        logger.info(
            "LLM request",
            model=settings.OPENAI_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        try:
            resp = await self._client.post(OPENAI_URL, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"LLM request timed out after {settings.LLM_TIMEOUT_SECONDS}s") from exc
        except httpx.RequestError as exc:
            raise LLMNetworkError(f"Network error: {exc}") from exc

        if resp.status_code != 200:
            body = resp.text
            logger.error("OpenAI API error", status=resp.status_code, body=body[:500])
            raise LLMAPIError(f"OpenAI returned HTTP {resp.status_code}: {body[:200]}")

        data = resp.json()
        choice = data["choices"][0]
        text = choice["message"]["content"] or ""
        stop_reason = choice.get("finish_reason", "unknown")
        model_used = data.get("model", settings.OPENAI_MODEL)

        logger.info("LLM response received", stop_reason=stop_reason, chars=len(text))
        return LLMResponse(text=text, stop_reason=stop_reason, model=model_used)

    async def aclose(self) -> None:
        await self._client.aclose()


# ── Custom exceptions for clear error handling in calling code (e.g. retry on timeout, but not on parse error)

class LLMError(Exception):
    """Base class for all LLM-related errors."""


class LLMTimeoutError(LLMError):
    pass


class LLMNetworkError(LLMError):
    pass


class LLMAPIError(LLMError):
    pass


class LLMParseError(LLMError):
    pass
