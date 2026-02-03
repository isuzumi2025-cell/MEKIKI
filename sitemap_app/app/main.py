from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints
from app.core.config import settings
from app.db.database import engine, Base
import sys
import asyncio
import os

# Fix for Playwright on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.include_router(endpoints.router, prefix=settings.API_V1_STR, tags=["sitemap"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def root():
    return FileResponse("app/static/index.html")
