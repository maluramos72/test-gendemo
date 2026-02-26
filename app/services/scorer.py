"""
app/services/scorer.py
──────────────────────
Scoring heurístico en 5 dimensiones para evaluar la calidad de casos de prueba generados por LLMs.

5 Dimensiones (weights sum to 1.0):

** Dimension       ->  Peso  -> Descripcion                                    
* quantity         ->  0.20  -> Penaliza pocos casos; satura en 3+ casos generados   
* steps_depth      ->  0.25  -> Promedio de pasos por caso; premia 3+ pasos por ser ejecutables    
* preconditions    ->  0.20  -> Penaliza precondiciones genéricas o vacías       
* expected_results ->  0.20  -> Penaliza palabras vagas ("funciona", "ok", "correcto", etc.)
* diversity        ->  0.15  -> Palabras únicas entre títulos (cobertura temática)

score = (cantidad × 0.20) + (pasos × 0.25) + (precondiciones × 0.20) + (resultados × 0.20) + (diversidad × 0.15)
score: 0.0 y 1.0 = label: Alta calidad / Calidad media / Mejorable
"""

from __future__ import annotations

import re
from typing import List

from app.core.models import QualityDimension, QualityReport, TestCase

# Patterns
_VAGUE = re.compile(
    r"\b(works|correct(ly)?|properly|fine|good|ok|okay|done|success|funciona|correcto|bien)\b",
    re.IGNORECASE,
)
_GENERIC_PRECOND = re.compile(
    r"^(the user is (logged in|on the app|in the system)|n/?a|none|ninguna?|no aplica)$",
    re.IGNORECASE,
)


def score_test_cases(test_cases: List[TestCase]) -> QualityReport:
    n = len(test_cases)

    # ── Quantity 
    qty = min(n / 3, 1.0) * 0.20

    # ── Steps_depth 
    avg_steps = sum(min(len(tc.steps) / 3, 1.0) for tc in test_cases) / n
    steps = avg_steps * 0.25

    # ── Preconditions specificity 
    def prec_score(tc: TestCase) -> float:
        p = tc.preconditions.strip()
        if _GENERIC_PRECOND.match(p):
            return 0.2
        return 1.0 if len(p) > 25 else 0.6

    prec = sum(prec_score(tc) for tc in test_cases) / n * 0.20

    # ── Expected result specificity 
    def res_score(tc: TestCase) -> float:
        vague_count = len(_VAGUE.findall(tc.expected_result))
        if vague_count == 0 and len(tc.expected_result) > 35:
            return 1.0
        if vague_count <= 1:
            return 0.7
        return 0.3

    res = sum(res_score(tc) for tc in test_cases) / n * 0.20

    # ── Title diversity
    words = {w for tc in test_cases for w in tc.title.lower().split()}
    div = min(len(words) / (n * 3), 1.0) * 0.15

    # ── Aggregate
    total = round(qty + steps + prec + res + div, 4)

    pct = round(total * 100)
    if pct >= 75:
        label = "Alta calidad"
    elif pct >= 50:
        label = "Calidad media"
    else:
        label = "Mejorable"

    dimensions = QualityDimension(
        quantity=round(qty / 0.20, 4),
        steps_depth=round(avg_steps, 4),
        preconditions=round(prec / 0.20, 4),
        expected_results=round(res / 0.20, 4),
        diversity=round(div / 0.15, 4),
    )

    return QualityReport(score=total, label=label, dimensions=dimensions)
