import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
logger = setup_logging()
request_logger = logger.getChild("request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up StudyApp backend...")
    try:
        from app.db.session import init_db
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    try:
        from app.tasks.processing import sweep_stale_jobs
        swept = sweep_stale_jobs()
        if swept:
            logger.warning(
                "Marked %d processing job(s) failed on startup (interrupted by previous restart)", swept,
            )
    except Exception as e:
        logger.error(f"Stale job sweep failed: {e}")
    try:
        from app.tasks.demo_seed import ensure_demo_seeded
        ensure_demo_seeded()
        logger.info("Demo content seeded")
    except Exception as e:
        logger.warning(f"Demo seeding skipped: {e}")
    yield
    logger.info("Shutting down StudyApp backend")


app = FastAPI(
    title="StudyAI - Lecture Knowledge System",
    description="AI-powered lecture-to-study-guide platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Lightweight request-timing log (no external monitoring stack needed to
    get P95/latency numbers locally — grep/awk the access log)."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    request_logger.info(
        "%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Safety net: log the real exception server-side, never leak it to the client."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal error, please retry."})


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.lectures import router as lectures_router
from app.api.routes.topics import router as topics_router
from app.api.routes.study_guide import router as study_guide_router
from app.api.routes.search import router as search_router
from app.api.routes.ask import router as ask_router
from app.api.routes.quiz import router as quiz_router
from app.api.routes.demo import router as demo_router
from app.api.routes.dashboard import router as dashboard_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(courses_router, prefix="/api/courses", tags=["courses"])
app.include_router(lectures_router, prefix="/api/lectures", tags=["lectures"])
app.include_router(topics_router, prefix="/api", tags=["topics"])
app.include_router(study_guide_router, prefix="/api", tags=["study-guide"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(ask_router, prefix="/api/ask", tags=["ask"])
app.include_router(quiz_router, prefix="/api/quiz", tags=["quiz"])
app.include_router(demo_router, prefix="/api/demo", tags=["demo"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
