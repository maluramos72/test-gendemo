"""
app/services/generator.py
─────────────────────────
Orchestrator: coordinates LLM call → validation → retry → scoring.
Estrategia de reintento: 
* Hasta MAX_RETRIES intentos en LLMParseError (JSON mal formado). 
* En LLMTimeoutError / LLMNetworkError → falla rápidamente (sin reintento; problema de infraestructura). 
* Tras agotar todos los reintentos → se envía a la capa de API para HTTP 502
"""

from __future__ import annotations

from app.core.config import settings
from app.core.models import GenerateResponse, ResponseMeta
from app.services.llm_client import LLMClient, LLMError, LLMParseError, LLMTimeoutError, LLMNetworkError
from app.services.scorer import score_test_cases
from app.services.validator import parse_and_validate
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_test_cases(user_story: str, client: LLMClient) -> GenerateResponse:
    """
    Full pipeline: user_story → LLM → validate → (retry?) → score → response.

    Raises:
       En LLMTimeoutError / LLMNetworkError → falla rápidamente (sin reintento; problema de infraestructura)
       LLMParseError: parseo fallido después de todos los reintentos.
    """
    attempts = 0
    last_error: Exception | None = None

    for attempt in range(1, settings.MAX_RETRIES + 2):  # +1 for zero-indexed range
        attempts = attempt
        logger.info("Generation attempt", attempt=attempt, max=settings.MAX_RETRIES + 1)

        try:
            # ── Step 1: Call LLM 
            llm_resp = await client.generate(user_story)

            # ── Step 2: Parse + Validate + Repair
            llm_output, was_repaired = parse_and_validate(
                raw=llm_resp.text,
                stop_reason=llm_resp.stop_reason,
            )

            # ── Step 3: Quality Score 
            quality = score_test_cases(llm_output.test_cases)

            logger.info(
                "Pipeline complete",
                attempt=attempt,
                test_cases=len(llm_output.test_cases),
                quality_score=quality.score,
                quality_label=quality.label,
                was_repaired=was_repaired,
            )

            return GenerateResponse(
                test_cases=llm_output.test_cases,
                quality=quality,
                meta=ResponseMeta(
                    model=llm_resp.model,
                    stop_reason=llm_resp.stop_reason,
                    was_repaired=was_repaired,
                    attempts=attempts,
                ),
            )

        except LLMParseError as e:
            last_error = e
            logger.warning("Parse error on attempt", attempt=attempt, error=str(e))
            if attempt <= settings.MAX_RETRIES:
                logger.info("Retrying…")
                continue
            break

        except (LLMTimeoutError, LLMNetworkError):
            # Infra errors: bubble up immediately, no retry
            raise

    raise last_error or LLMParseError("Generation failed after all retries")
