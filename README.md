# QA Test Generator — AI Generic QA Engine Microservice

Transforma historias de usuario en casos de prueba estructurados usando un LLM.  
Genérico para cualquier dominio de software: auth, pagos, notificaciones, etc.

---

## Índice

1. [Arquitectura](#arquitectura)
2. [Estructura de archivos](#estructura-de-archivos)
3. [Instalación y ejecución local](#instalación-y-ejecución-local)
4. [Endpoints](#endpoints)
5. [Parámetros LLM justificados](#parámetros-llm-justificados)
6. [Estrategias de validación LLMOps](#estrategias-de-validación-llmops)
7. [Decisiones arquitectónicas](#decisiones-arquitectónicas)
8. [Trade-offs](#trade-offs)
9. [Estrategia de escalabilidad](#estrategia-de-escalabilidad)
10. [Consideraciones de costo](#consideraciones-de-costo)
11. [Mejoras posibles con más tiempo](#mejoras-posibles-con-más-tiempo)
12. [Tests](#tests)
13. [Tiempo estimado de desarrollo](#tiempo-estimado-de-desarrollo)

---

## Arquitectura

```
POST /api/v1/generate-tests
           │
           ▼
   ┌───────────────┐
   │  API Layer    │  routes.py + dependencies.py
   │  (FastAPI)    │
   └───────┬───────┘
           │  UserStoryRequest (validado por Pydantic)
           ▼
   ┌───────────────┐
   │  Orchestrator │  generator.py  - retry loop estructural (Layer 2)
   └───────┬───────┘
           │
     ┌─────┴──────┐
     │            │
     ▼            ▼
┌─────────┐  ┌──────────────┐
│   LLM   │  │  Validator   │  llm_client.py  - retry transporte (Layer 1)
│ Client  │  │  + Repair    │  validator.py   - validate_structure + repair_truncated_json
└────┬────┘  └──────┬───────┘
     │              │
     └──────┬───────┘
            │  list[TestCase] validado
            ▼
   ┌───────────────┐
   │Quality Scorer │  scorer.py  - 5 dimensiones heurísticas, costo LLM: $0
   └───────────────┘
            │
            ▼
   GenerateResponse (JSON)
   { test_cases, quality, meta }
```

### Capas del sistema

| Capa | Archivo(s) | Responsabilidad |
|------|-----------|-----------------|
| **API** | `routes.py`, `dependencies.py` | Recibe request, valida entrada, retorna response o error HTTP |
| **Orquestación** | `generator.py` | Coordina el flujo, maneja retry estructural (Layer 2) |
| **LLM Client** | `llm_client.py` | Llama OpenAI API, maneja retry de transporte (Layer 1), detecta `stop_reason` |
| **Validación** | `validator.py` | Repara JSON truncado, valida estructura del output del LLM |
| **Scoring** | `scorer.py` | Puntúa calidad heurística en 5 dimensiones sin costo adicional |
| **Modelos** | `core/models.py` | Contratos de datos (Pydantic v2): request, response, test case |
| **Prompts** | `core/prompts.py` | System prompt genérico, sin hardcoding de dominio |
| **Config** | `core/config.py` | Variables de entorno tipadas con pydantic-settings |
| **Logging** | `utils/logger.py` | Logging estructurado con structlog (JSON en prod, pretty en dev) |

---

## Estructura de archivos

```
Test-GenDemo/
├── app/
│   ├── main.py                   # FastAPI app, CORS, middleware de logging (request_id, duración)
│   ├── api/
│   │   ├── routes.py             # Endpoints REST: POST /generate-tests, GET /health, GET /examples
│   │   └── dependencies.py       # Inyección de dependencias (GeneratorService singleton)
│   ├── core/
│   │   ├── config.py             # Settings via pydantic-settings + validación de env vars
│   │   ├── models.py             # Pydantic v2: UserStoryRequest, TestCase, GenerateResponse
│   │   └── prompts.py            # System prompt genérico (sin hardcoding de dominio)
│   ├── services/
│   │   ├── llm_client.py         # Cliente OpenAI: retry transporte, stop_reason check, backoff
│   │   ├── validator.py          # repair_truncated_json() + validate_structure()
│   │   ├── scorer.py             # Quality score heurístico — 5 dimensiones ponderadas
│   │   └── generator.py          # Orquestador: retry estructural, coordina pipeline completo
│   └── utils/
│       └── logger.py             # Logging estructurado con structlog
├── tests/
│   └── test_validator.py         # Tests unitarios: repair, validate, scorer (sin API key)
├── docs/
│   ├── llmops-diagram.html       # Diagrama LLMOps completo (pipeline visual)
│   └── scoring-explainer.jsx     # Explicación interactiva del scoring heurístico
├── requirements.txt
├── .env                          # Variables de entorno 
├── frontend.html                 # Frontend del proyecto mas amigable 
├── run.py                        # Script de arranque: uvicorn con configuración
└── README.md
```

---

## Instalación y ejecución local

### ⚠️ Regla en Windows: ejecutar siempre desde la RAÍZ del proyecto

```
Test-GenDemo\          ← RAÍZ (aquí deben estar run.py y requirements.txt)
├── app\
├── run.py
└── requirements.txt
```

### Pasos

```bat
REM 1. Abrir terminal en la RAÍZ del proyecto
cd C:\Users\TuUsuario\Downloads\Test-GenDemo

REM 2. Crear entorno virtual (solo la primera vez)
python -m venv .venv

REM 3. Activar entorno virtual
.venv\Scripts\activate

REM 4. Instalar dependencias
pip install -r requirements.txt

REM 5. Configurar variables de entorno
REM    Abrir .env y editar: OPENAI_API_KEY=sk-...

REM 6. Levantar el servidor
python run.py
REM    Alternativa: uvicorn app.main:app --reload

REM 7. Abrir documentación interactiva
REM    http://127.0.0.1:8000/docs
```

### Variables de entorno requeridas (`.env`)

```env
# Requerida
OPENAI_API_KEY=sk-...

# Opcionales (valores por defecto)
ENVIRONMENT=development        # development | production
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2048            # NO bajar de 1500 — riesgo de truncado
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=3
LOG_LEVEL=INFO
```

###  Error frecuente — "No module named 'app'"

```
ModuleNotFoundError: No module named 'app'
```

**Causa:** estás ejecutando uvicorn **dentro** de `app\`:

```bat
REM  MAL
cd app
uvicorn main:app --reload

REM  BIEN — desde la raíz
cd C:\Users\TuUsuario\Downloads\Test-GenDemo
python run.py
```

---

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Health check del servicio |
| `GET` | `/api/v1/examples` | Historias de usuario de ejemplo (5 dominios) |
| `POST` | `/api/v1/generate-tests` | Genera casos de prueba desde una historia de usuario |
| `GET` | `/docs` | Swagger UI interactivo |

### Request

```json
{
  "user_story": "Como usuario quiero recuperar mi contraseña para poder acceder nuevamente al sistema."
}
```

### Response

```json
{
  "test_cases": [
    {
      "title": "Happy Path – Password Recovery Email Sent",
      "preconditions": "User account exists with verified email; user is on the password recovery page",
      "steps": [
        "Enter registered email address in the recovery field",
        "Click 'Send recovery link'",
        "Check email inbox"
      ],
      "expected_result": "Recovery email arrives within 60s; link opens a valid password-reset form"
    }
  ],
  "quality": {
    "score": 0.84,
    "label": "Alta calidad",
    "dimensions": {
      "quantity": 1.0,
      "steps_depth": 0.89,
      "preconditions": 0.95,
      "expected_results": 1.0,
      "diversity": 0.78
    }
  },
  "meta": {
    "model": "gpt-4o-mini",
    "stop_reason": "stop",
    "was_repaired": false,
    "attempts": 1,
    "pipeline": "user_story → prompt → LLM → validate+repair → quality_score → response"
  }
}
```

---

## Parámetros LLM justificados

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `temperature` | `0.3` | Baja aleatoriedad → output JSON determinístico y consistente entre llamadas |
| `max_tokens` | `2048` | 4 casos × ~400 tokens c/u + overhead del prompt.
| `top_p` | `0.95` | Nucleus sampling complementario; elimina probabilidades de cola que generan tokens extraños |
| `model` | `gpt-4o-mini` | Mejor balance costo/calidad para generación de JSON estructurado. Configurable vía env var |
| `response_format` | `json_object` | Fuerza JSON válido a nivel de API — elimina el 90% de errores de parsing |

---

## Estrategias de validación LLMOps

El pipeline de decisión **5 capas** 

**1 Recibir la historia de usuario**
FastAPI valida el body con Pydantic. Si el input es inválido, atrapado si falla con HTTP 422 — sin llegar al LLM.

**2 Diseñar un prompt genérico**
Sin hardcoding de dominio. El mismo prompt debe funcionar para auth, e-commerce, mobile, APIs — el LLM infiere el vocabulario correcto.

**3 Llamar al LLM con parámetros justificados**
temperature=0.3 para determinismo. max_tokens=2048 porque 1024 causaba truncado en dominios complejos.

**4 Validar, detectar truncado y reparar**
Si stop_reason='length' → activar repair antes de intentar JSON.parse. Si el JSON está malformado → 3 estrategias de reparación.

**5 Calcular quality score y responder**
Score heurístico de 5 dimensiones. Respuesta estructurada con metadata para observabilidad.

| Dimensión | Peso | Penaliza cuando |
|-----------|------|-----------------|
| **Cantidad** | 0.20 | Menos de 3 casos generados |
| **Profundidad de pasos** | 0.25 | Menos de 3 pasos por caso |
| **Precondiciones** | 0.20 | Frases genéricas ("the user is logged in") |
| **Resultados esperados** | 0.20 | Palabras vagas: "works", "ok", "correct" |
| **Diversidad** | 0.15 | Títulos con vocabulario repetitivo |

---

## Decisiones arquitectónicas

### Separación estricta de responsabilidades

Cada módulo tiene una sola razón para cambiar. El `llm_client.py` puede reemplazarse por un cliente de Gemini o Claude sin tocar el orquestador. El `scorer.py` puede evolucionar a una autoevaluación LLM sin afectar el resto del pipeline.

### Prompt genérico sin hardcoding de dominio

`core/prompts.py` no contiene lógica específica de ningún dominio. El LLM actúa como QA Engineer que aplica su conocimiento al contexto de cada historia. Esto es lo que hace el sistema verdaderamente genérico: "recuperar contraseña" produce tokens/lockout/sesiones; "carrito de compras" produce inventario/checkout/precios — sin ninguna regla explícita en el código.

### Dos capas de retry independientes

Los fallos de transporte (red, rate limits) y los fallos de contenido (shape del JSON) tienen causas distintas y merecen estrategias distintas. Mezclarlos en un solo retry loop produciría reintentos innecesarios en casos donde solo un tipo falló.

### FastAPI + async/await

Las llamadas al LLM son I/O bound. Un modelo async permite que un solo proceso maneje múltiples requests concurrentes mientras espera respuesta de OpenAI, sin bloquear el event loop.

### Stateless por diseño

El servicio no mantiene estado entre requests. Esto no es un accidente — es una decisión deliberada que habilita el escalado horizontal sin coordinación entre instancias.

### Pydantic v2 como contrato de datos

Los modelos en `core/models.py` son la fuente de verdad del contrato. La validación ocurre en el borde del sistema (entrada del request) y en el borde del LLM (salida del modelo), no en la lógica intermedia.

---

## Trade-offs

| Decisión | Ventaja | Costo |
|----------|---------|-------|
| Sin base de datos | Simplicidad total, zero operaciones de DB, fácil de desplegar | Sin historial de generaciones, sin cache persistente, sin analytics |
| Scoring heurístico vs segundo LLM | Costo $0, latencia ~0ms adicional | Cubre el 80% de casos; puede pasar resultados borderline |
| `response_format: json_object` | Elimina 90% de errores de parsing | Solo disponible en modelos OpenAI recientes; no portable a todos los LLMs |
| Retry a nivel de aplicación (Layer 2) | Maneja shape incorrecto independientemente del transporte | Puede duplicar latencia en peor caso (3 intentos × 5s = 15s) |
| Servicio stateless | Escala horizontalmente sin coordinación | Cada request reconstruye el contexto desde cero; sin memoria entre llamadas |
| `gpt-4o-mini` como default | ~10× más barato que `gpt-4o` | Menor capacidad de razonamiento; puede generar casos menos específicos en dominios muy técnicos |


## Consideraciones de costo

### Costo por request (estimado)

| Componente | Tokens promedio | Costo (gpt-4o-mini) |
|------------|-----------------|---------------------|
| System prompt + user story | ~450 tokens | ~$0.000068 |
| Completion (4 test cases) | ~700 tokens | ~$0.00042 |
| **Total por request** | **~1150 tokens** | **~$0.00049** |

### Proyección a escala

| Volumen | Costo diario | Costo mensual |
|---------|-------------|---------------|
| 100 req/día | ~$0.05 | ~$1.50 |
| 1 000 req/día | ~$0.49 | ~$14.70 |
| 10 000 req/día | ~$4.90 | ~$147 |
| 100 000 req/día | ~$49 | ~$1 470 |


---

## Mejoras posibles con más tiempo

Las siguientes mejoras están ordenadas por impacto estimado / esfuerzo:

### Alta prioridad
**Soporte multi-modelo**  
Abstraer `llm_client.py` detrás de una interfaz `LLMProvider` con implementaciones para Claude Sonnet, Gemini Pro y Ollama (modelos locales). Permite comparar calidad por dominio y tener fallback si OpenAI tiene downtime.

### Prioridad media
**Persistencia de generaciones**  
Guardar (historia de usuario, test cases generados) en PostgreSQL. Habilita: analytics de calidad por dominio, dataset para fine-tuning, historial por equipo/proyecto.

### Prioridad baja
**Support para historias largas**  
Para user stories con contexto extendido que requieren más tokens, procesar de forma asíncrona.
**Fine-tuning**  
Con ~500 (historia, test cases de alta calidad) acumulados, un modelo fine-tuned podría generar output de mayor calidad con menor temperatura y menos tokens. Costo de fine-tuning: ~$5–20 por run de entrenamiento.

---

## Tests

```bash
# Ejecutar todos los tests (no requiere API key — LLM mockeado)
pytest tests/ -v

# Tests específicos
pytest tests/test_validator.py -v -k "repair"    # solo tests de reparación JSON
pytest tests/test_validator.py -v -k "scorer"    # solo tests del quality scorer
```

Los tests cubren:
- `validate_structure()`: claves faltantes, lista vacía, tipos incorrectos
- `repair_truncated_json()`: truncado mid-string, mid-object, backticks, trailing commas, caso irrecuperable
- `compute_quality_score()`: casos buenos, vague results, rango 0.0–1.0, no lanza excepciones

---

## Tiempo estimado de desarrollo

| Fase | Descripción | Tiempo |
|------|-------------|--------|
| Setup y estructura del proyecto | FastAPI skeleton, config, logging, modelos Pydantic | 90 min |
| `core/prompts.py` | Diseño del system prompt genérico, pruebas iterativas de output | 90 min |
| `llm_client.py` | Cliente OpenAI, retry Layer 1, backoff, stop_reason check | 60 min |
| `validator.py` | `validate_structure()` + `repair_truncated_json()` (9 pasos) | 120 min |
| `scorer.py` | Scorer heurístico 5 dimensiones, calibración de pesos | 120 min |
| `generator.py` | Orquestador, retry Layer 2, manejo de errores | 90 min |
| `api/routes.py` + `dependencies.py` | Endpoints REST, error mapping, inyección de dependencias | 45 min |
| Tests unitarios | `test_validator.py`: repair, validate, scorer sin API key | 45 min |
| Documentación | README completo, diagramas LLMOps, scoring explainer | 140 min |
| **Total** | | **~14 horas** | **~4-5 hrs diarias**| | **~4 dias** |

> El tiempo mayor fue en: 
  `validator.py` (repair robusto) 
  `core/prompts.py` (prompt engineering iterativo). La calidad del prompt tiene el mayor impacto en la calidad del output final.
  `scorer.py` (calculo del scoring heuristico)