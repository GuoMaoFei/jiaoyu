import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv

# Load .env into os.environ before any other imports that use os.getenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.config import get_settings
from app.database import get_db

settings = get_settings()

# === Logging Setup (Java-style: console + file, leveled, rotated) ===
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

log_level = logging.DEBUG if settings.DEBUG else logging.INFO

_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Console handler
_console = logging.StreamHandler()
_console.setLevel(log_level)
_console.setFormatter(_formatter)

# app.log — all INFO+ (rotated 10MB x 5)
_app_file = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
_app_file.setLevel(logging.INFO)
_app_file.setFormatter(_formatter)

# error.log — only ERROR+ (rotated 10MB x 5)
_err_file = RotatingFileHandler(LOG_DIR / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
_err_file.setLevel(logging.ERROR)
_err_file.setFormatter(_formatter)

# Root logger: console + files
_root = logging.getLogger()
_root.setLevel(log_level)
_root.addHandler(_console)
_root.addHandler(_app_file)
_root.addHandler(_err_file)

# Suppress noisy third-party loggers
for _name in ["httpcore", "httpx", "aiosqlite", "multipart", "anthropic._base_client"]:
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Enable LangChain Debug Logging only in debug mode
from langchain_core.globals import set_debug

set_debug(settings.DEBUG)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for TreeEdu Agent powered by LangGraph & PageIndex",
)

# CORS middleware for frontend integration
allowed_origins = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]
if settings.ENVIRONMENT == "development":
    allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# === Register Routers ===
from app.routers import auth, chat, materials, student, lesson, report, exam, quiz, knowledge_points

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(materials.router)
app.include_router(student.router)
app.include_router(lesson.router)
app.include_router(report.router)
app.include_router(exam.router)
app.include_router(quiz.router)
app.include_router(knowledge_points.router)


# === Probe Endpoints ===


@app.get("/health", tags=["Probes"])
async def health_check():
    """Liveness probe endpoint."""
    return {"status": "ok", "version": settings.VERSION}


@app.get("/api/db_test", tags=["Probes"])
async def db_test(db: AsyncSession = Depends(get_db)):
    """Readiness probe to check DB connection."""
    try:
        result = await db.execute(text("SELECT 1"))
        val = result.scalar()
        return {"status": "ok", "db_connected": val == 1}
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        return JSONResponse(status_code=503, content={"status": "error", "message": "Database unavailable"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
