"""
QA Test Generator – FastAPI Microservice
Entry point: python run.py  →  http://127.0.0.1:8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).parent.parent   # project root (where frontend.html lives)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀  QA Engine starting", version=settings.APP_VERSION, env=settings.ENV)
    logger.info(f"🌐  Frontend → http://127.0.0.1:8000")
    yield
    logger.info("🛑  QA Engine shutting down")


app = FastAPI(
    title="QA Test Generator",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes 
app.include_router(router, prefix="/api/v1")


# ── Serve frontend.html at / and static assets from /static
@app.get("/", include_in_schema=False)
async def serve_frontend():
    html_file = ROOT / "frontend.html"
    if html_file.exists():
        return FileResponse(html_file, media_type="text/html")
    return JSONResponse({"detail": "frontend.html not found in project root"}, status_code=404)


# ── Global error handler – logs unhandled exceptions and returns generic error response
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception", error=str(exc), path=str(request.url))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
