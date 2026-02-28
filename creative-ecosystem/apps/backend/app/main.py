"""
ICC Backend — FastAPI Gateway Application

Entry point for the Integrated Creative Ecosystem (ICC) backend.
Aggregates MEKIKI OCR, Storyboard, Sitemap, Vault, Orchestra, and FlowForge
proxy APIs under a single gateway.

Usage:
    cd creative-ecosystem/apps/backend
    python run.py                  # production (reload=True)
    uvicorn app.main:app --reload  # development
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import (
    flowforge_proxy,
    mekiki,
    orchestra,
    sitemap,
    storyboard,
    vault,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("icc-backend")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log all registered routes on startup."""
    logger.info("ICC Backend starting up …")
    logger.info("Registered routes:")
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", str(route))
        if methods:
            logger.info("  %s  %s", ", ".join(sorted(methods)), path)
        else:
            logger.info("  MOUNT  %s", path)
    yield
    logger.info("ICC Backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ICC Gateway API",
    description=(
        "Integrated Creative Ecosystem — unified gateway for MEKIKI OCR, "
        "Storyboard planning, Sitemap crawling, Vault search, Orchestra sessions, "
        "and FlowForge rendering."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite / React dev server
        "http://localhost:3001",  # FlowForge dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler — 500 Internal Server Error
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return a structured 500 response.

    Logs the full traceback to aid debugging without leaking internals to
    the client in production.
    """
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "type": type(exc).__name__,
            # Only expose message when debug is enabled
            "message": str(exc) if settings.debug else None,
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["meta"],
    summary="Gateway health check",
)
def health() -> dict:
    """Return a minimal health payload.

    Consumed by Docker health checks, load balancers, and the FlowForge
    proxy status endpoint.
    """
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Routers — all mounted under /api/v1
# ---------------------------------------------------------------------------
_API_PREFIX = "/api/v1"

app.include_router(mekiki.router, prefix=_API_PREFIX)
app.include_router(storyboard.router, prefix=_API_PREFIX)
app.include_router(sitemap.router, prefix=_API_PREFIX)
app.include_router(vault.router, prefix=_API_PREFIX)
app.include_router(orchestra.router, prefix=_API_PREFIX)
app.include_router(flowforge_proxy.router, prefix=_API_PREFIX)
