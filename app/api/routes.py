"""
app/api/routes.py
─────────────────
REST API endpoints.

POST /api/v1/generate-tests
    Body: { "user_story": "..." }
    Returns: GenerateResponse (test cases + quality score + metadata)

GET  /api/v1/examples
    Returns predefined example user stories for quick testing.

Error handling:
  • 422: Pydantic validation error (bad request body) → FastAPI default
  • 504: LLM timeout
  • 502: LLM network or parse error
  • 500: Unexpected (caught by global handler in main.py)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.models import GenerateRequest, GenerateResponse
from app.api.dependencies import get_llm_client
from app.services.generator import generate_test_cases
from app.services.llm_client import LLMClient, LLMParseError, LLMTimeoutError, LLMNetworkError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

EXAMPLES = [
    {"label": "🔑 Recuperar contraseña", "story": "Como usuario quiero recuperar mi contraseña para poder acceder nuevamente al sistema."},
    {"label": "🛒 Carrito de compras",   "story": "Como cliente quiero agregar productos a mi carrito para poder comprarlos más tarde."},
    {"label": "📁 Subir archivos",       "story": "Como usuario quiero subir documentos PDF a mi perfil para tener mis archivos disponibles en la nube."},
    {"label": "🔔 Notificaciones",       "story": "Como usuario quiero recibir notificaciones push cuando hay una nueva oferta disponible."},
    {"label": "💳 Pago con tarjeta",     "story": "Como cliente quiero pagar mi orden con tarjeta de crédito para completar mi compra de forma segura."},
]


@router.post(
    "/generate-tests",
    response_model=GenerateResponse,
    summary="Generate QA test cases from a user story",
    tags=["QA Engine"],
)
async def generate_tests(
    body: GenerateRequest,
    client: LLMClient = Depends(get_llm_client),
) -> GenerateResponse:
    logger.info("Request received", story_length=len(body.user_story))

    try:
        return await generate_test_cases(user_story=body.user_story, client=client)

    except LLMTimeoutError as e:
        logger.error("LLM timeout", error=str(e))
        raise HTTPException(status_code=504, detail=f"LLM request timed out: {e}")

    except LLMNetworkError as e:
        logger.error("LLM network error", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM network error: {e}")

    except LLMParseError as e:
        logger.error("LLM parse error after retries", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM returned unparseable output: {e}")


@router.get("/examples", summary="Get example user stories", tags=["QA Engine"])
async def get_examples() -> list[dict]:
    return EXAMPLES
