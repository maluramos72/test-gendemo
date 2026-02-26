"""
app/services/validator.py
─────────────────────────
Validación estructural y reparación de JSON para la salida del LLM

Pasos de validación y reparación:
  1. Eliminar los delimitadores de markdown (```json … ```) si existen.
  2. Intentar JSON.parse directamente. Si falla y stop_reason es "length", proceder a reparación.
  3. Reparación heurística para JSON truncado:
     a. Eliminar fragmentos de string incompletos al final.
     b. Eliminar claves sin valor al final (e.g. , "expected_result":).
     c. Eliminar claves incompletas (sin comillas de cierre).
     d. Eliminar comas finales antes de } o ].
     e. Contar delimitadores { [ y cerrar los que falten al final.
  4. Validar la estructura resultante contra el modelo Pydantic LLMOutput.
  5. Si todo falla, lanzar LLMParseError con detalles diagnósticos para facilitar debugging 
  (stop_reason, fragmento de raw, error específico).
  
  Esto refleja la función repairTruncatedJson() del JSX original, portada fielmente a Python 
  con validación estructural adicional de Pydantic.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.core.models import LLMOutput
from app.services.llm_client import LLMParseError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def strip_fences(raw: str) -> str:
    """ Elimina las comillas invertidas de markdown que el LLM a veces agrega a pesar de las instrucciones. """
    return re.sub(r"```(?:json)?|```", "", raw).strip()


def repair_truncated_json(raw: str) -> dict:
    """
    Intenta salvar una cadena JSON truncada a mitad de camino (stop_reason='length').

    Algoritmo:
        1. Eliminar la cadena literal abierta/incompleta al final.
        2. Eliminar la clave final que no tiene valor.
        3. Eliminar la clave final incompleta (sin comillas de cierre).
        4. Eliminar comas finales antes de los delimitadores de cierre.
        5. Contar las { y [ no emparejadas y cerrarlas en orden inverso.
        6. Limpieza final de comas después de cerrar.
    """
    s = strip_fences(raw)

    # Try as-is first
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Strip truncated string at end
    s = re.sub(r',?\s*"(?:[^"\\]|\\.)*$', "", s)
    # Strip key with no value  e.g.  , "expected_result":
    s = re.sub(r',?\s*"[^"]*"\s*:\s*$', "", s)
    # Strip incomplete key (no closing quote)
    s = re.sub(r',?\s*"[^"]*$', "", s)
    # Strip trailing commas before ] or }
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    s = re.sub(r",\s*$", "", s)

    # Count unmatched delimiters (state machine ignoring string contents)
    braces = brackets = 0
    in_str = esc = False
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            braces += 1
        elif ch == "}":
            braces -= 1
        elif ch == "[":
            brackets += 1
        elif ch == "]":
            brackets -= 1

    s += "]" * max(0, brackets)
    s += "}" * max(0, braces)
    # Final trailing-comma cleanup after closing
    s = re.sub(r",(\s*[}\]])", r"\1", s)

    return json.loads(s)  # raises JSONDecodeError if still broken


def parse_and_validate(raw: str, stop_reason: str) -> tuple[LLMOutput, bool]:
    """
    Parseo y validación de la salida cruda del LLM. Devuelve (LLMOutput, was_repaired).
    Returns:
        (LLMOutput, was_repaired)
    Raises:
        LLMParseError: si parseo o validación falla después de todas las estrategias.
    """
    cleaned = strip_fences(raw)
    was_repaired = False

    # ── Strategy A: direct parse 
    if stop_reason != "length":
        try:
            data = json.loads(cleaned)
            return _validate_structure(data), False
        except json.JSONDecodeError as e:
            logger.warning("Direct JSON parse failed, attempting repair", error=str(e))

    # ── Strategy B: repair truncated JSON 
    try:
        data = repair_truncated_json(cleaned)
        was_repaired = True
        logger.info("JSON repaired successfully")
        return _validate_structure(data), True
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMParseError(
            f"JSON could not be parsed or repaired. stop_reason={stop_reason!r}. "
            f"Detail: {e}. First 300 chars of raw: {raw[:300]!r}"
        ) from e


def _validate_structure(data: dict) -> LLMOutput:
    """ Valida el dict contra el esquema LLMOutput. Lanza LLMParseError en caso de fallo. """
    
    try:
        return LLMOutput(**data)
    except (ValidationError, TypeError) as e:
        raise LLMParseError(f"Structural validation failed: {e}") from e
