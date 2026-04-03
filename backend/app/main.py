"""FastAPI application entry point for PhishTrack."""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.cases import router as cases_router
from app.api.webhooks import router as webhooks_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.config import router as config_router
from app.api.email_templates import router as email_templates_router
from app.api.evidence import router as evidence_router
from app.api.reports import router as reports_router
from app.api.stats import router as stats_router
from app.api.public import router as public_router
from app.api.submissions import router as submissions_router
from app.api.blacklist import router as blacklist_router
from app.api.whitelist import router as whitelist_router
from app.api.migrations import router as migrations_router
from app.api.roles import router as roles_router
from app.api.hunting import router as hunting_router
from app.config import settings
from app.database import init_db, close_db
from app.schemas import HealthResponse
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan management.

    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    print(f"Debug mode: {settings.DEBUG}")

    # Initialize database
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("Continuing anyway - tables will be created on first use if possible")

    yield

    # Shutdown
    print("Shutting down...")
    await close_db()
    print("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Automated phishing takedown system with OSINT analysis and email reporting",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS - must be added before exception handlers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "code": exc.status_code,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General exception handler."""
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "code": 500,
            }
        },
    )


# Root endpoint
@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Automated phishing takedown system",
        "docs": "/docs" if settings.DEBUG else "disabled in production",
        "api": settings.API_PREFIX,
    }


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint for monitoring.

    Returns:
        HealthResponse with service status
    """
    # Check database
    db_status = "ok"
    try:
        from app.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    # Check Celery
    celery_status = "ok"
    try:
        from app.tasks.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2)
        stats = inspect.stats()
        if not stats:
            celery_status = "no workers"
    except Exception as e:
        celery_status = f"error: {str(e)[:50]}"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        celery=celery_status,
    )


# API routers
app.include_router(public_router, prefix=settings.API_PREFIX)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(users_router, prefix=settings.API_PREFIX)
app.include_router(config_router, prefix=settings.API_PREFIX)
app.include_router(email_templates_router, prefix=settings.API_PREFIX)
app.include_router(evidence_router, prefix=settings.API_PREFIX)
app.include_router(cases_router, prefix=settings.API_PREFIX)
app.include_router(webhooks_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)
app.include_router(stats_router, prefix=settings.API_PREFIX)
app.include_router(submissions_router, prefix=settings.API_PREFIX)
app.include_router(blacklist_router, prefix=settings.API_PREFIX)
app.include_router(whitelist_router, prefix=settings.API_PREFIX)
app.include_router(migrations_router, prefix=settings.API_PREFIX, tags=["migrations"])
app.include_router(roles_router, prefix=settings.API_PREFIX)
app.include_router(hunting_router, prefix=settings.API_PREFIX)

# Static files mount for templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Startup event for additional initialization
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks."""
    print(f"API available at http://{settings.HOST}:{settings.PORT}{settings.API_PREFIX}")
    print(f"CORS origins: {settings.CORS_ORIGINS}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
