"""
app/core/models.py
──────────────────
Pydantic v2 models for request validation and response serialization.
These models enforce the JSON schema that the LLM must produce.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── LLM output schema 

class TestCase(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    preconditions: str = Field(..., min_length=5, max_length=200)
    steps: List[str] = Field(..., min_length=2, max_length=4)
    expected_result: str = Field(..., min_length=10, max_length=200)

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: List[str]) -> List[str]:
        if any(not s.strip() for s in v):
            raise ValueError("Steps must not contain empty strings")
        return v


class LLMOutput(BaseModel):
    test_cases: List[TestCase] = Field(..., min_length=1)


# ── API contracts 

class GenerateRequest(BaseModel):
    user_story: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="User story in natural language",
        examples=["Como usuario quiero recuperar mi contraseña para poder acceder nuevamente al sistema."],
    )


class QualityDimension(BaseModel):
    quantity: float = Field(..., ge=0, le=1, description="Score for number of test cases")
    steps_depth: float = Field(..., ge=0, le=1, description="Score for step depth")
    preconditions: float = Field(..., ge=0, le=1, description="Score for precondition quality")
    expected_results: float = Field(..., ge=0, le=1, description="Score for result specificity")
    diversity: float = Field(..., ge=0, le=1, description="Score for title/topic diversity")


class QualityReport(BaseModel):
    score: float = Field(..., ge=0, le=1, description="Aggregate quality score 0-1")
    label: str
    dimensions: QualityDimension


class StopReason(str, Enum):
    end_turn = "stop"
    max_tokens = "length"
    unknown = "unknown"


class GenerateResponse(BaseModel):
    test_cases: List[TestCase]
    quality: QualityReport
    meta: "ResponseMeta"


class ResponseMeta(BaseModel):
    model: str
    stop_reason: str
    was_repaired: bool
    attempts: int
    pipeline: str = "user_story → prompt → LLM → validate+repair → quality_score → response"


GenerateResponse.model_rebuild()
