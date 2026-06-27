# backend/app/main.py

"""
FastAPI application entrypoint.

Creates the app, configures logging, registers exception handlers and
routers, and manages startup/shutdown lifecycle (database engine disposal
on shutdown). Future routers (search, conversations, documents, settings)
are registered in the same place auth's router is, as they land in later
batches.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.auth import router as auth_router
from app.api.v1.search import router as search_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine
from app.exceptions import NovaMindError


# Import all ORM models so SQLAlchemy's mapper registry has every class
# registered before any request triggers mapper configuration. Without
# this, string-based relationship() references like "Conversation" fail
# at runtime when only User is imported through the auth dependency chain.
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.search import Search  # noqa: F401
from app.models.source import Source  # noqa: F401
from app.models.user import User  # noqa: F401

APP_VERSION = "0.1.0"

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info(
        "Starting NovaMind backend",
        extra={"app_env": settings.APP_ENV, "version": APP_VERSION},
    )
    yield
    logger.info("Shutting down NovaMind backend")
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "NovaMind is an AI-powered answer engine that searches the web in "
        "real time, synthesizes cited answers from multiple sources, and "
        "supports conversational follow-up — built on NVIDIA NIM inference "
        "with Tavily and Brave search."
    ),
    version=APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NovaMindError)
async def novamind_error_handler(request: Request, exc: NovaMindError) -> JSONResponse:
    """
    Maps every application-raised NovaMindError (and its subclasses —
    AuthError, SearchError, LLMError, DocumentError, etc.) to a consistent
    JSON error response using each exception's own status_code/error_code.
    """
    logger.warning(
        "Handled application error",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches anything that is not a NovaMindError — a true bug or an
    unexpected third-party library error. Logs the full exception server-
    side but never leaks internal details to the client.
    """
    logger.error(
        "Unhandled exception",
        extra={"path": request.url.path, "exception_type": type(exc).__name__},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again.",
            "details": {},
        },
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness/readiness probe. Intentionally has no database or external
    dependency check in this batch — that arrives once search/document
    routers (and their providers) exist, so health reflects components
    that actually exist yet."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": APP_VERSION,
        "environment": settings.APP_ENV,
    }

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(search_router, prefix=settings.API_V1_PREFIX)