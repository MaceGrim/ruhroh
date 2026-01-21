"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db, close_db
from app.api import auth, documents, chat, search, admin, config as config_routes, eval as eval_routes
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.error_handlers import register_exception_handlers
from app.utils.logging import setup_logging

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    setup_logging(settings.log_level)
    logger.info("Starting ruhroh backend", version="0.1.0")

    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    await close_db()
    logger.info("Database connections closed")
    logger.info("Shutting down ruhroh backend")


app = FastAPI(
    title="ruhroh",
    description="Modular RAG Document Chat System API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Register exception handlers
register_exception_handlers(app)

# Add middleware (order matters - first added is outermost)
# CORS middleware first
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Request ID tracking
app.add_middleware(RequestIDMiddleware)

# Rate limiting
app.add_middleware(RateLimitMiddleware, settings=settings)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )

    return response


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(config_routes.router, prefix="/api/v1/config", tags=["config"])
app.include_router(eval_routes.router, prefix="/api/v1/eval", tags=["eval"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.db.database import check_db_health
    from app.services.qdrant import check_qdrant_health

    db_healthy = await check_db_health()
    qdrant_healthy = await check_qdrant_health()

    all_healthy = db_healthy and qdrant_healthy

    return {
        "status": "ok" if all_healthy else "degraded",
        "database": "ok" if db_healthy else "error",
        "qdrant": "ok" if qdrant_healthy else "error",
    }
