import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings
from app.database import get_db

settings = get_settings()

# Setup logging
log_level = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(level=log_level)
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
from app.routers import auth, chat, materials, student, lesson, report, exam

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(materials.router)
app.include_router(student.router)
app.include_router(lesson.router)
app.include_router(report.router)
app.include_router(exam.router)


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
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
