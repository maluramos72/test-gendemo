"""
app/api/dependencies.py
───────────────────────
FastAPI dependency injection.

LLMClient is created once per request via Depends().
For production scale, consider a connection pool or singleton pattern
with proper lifecycle management (lifespan events).
"""

from __future__ import annotations

from app.services.llm_client import LLMClient


async def get_llm_client() -> LLMClient:
    """Yields a fresh LLMClient per request. Cleans up on response completion."""
    client = LLMClient()
    try:
        yield client
    finally:
        await client.aclose()
