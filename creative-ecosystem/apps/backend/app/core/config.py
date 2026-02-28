"""
ICC Backend — Application Settings
Pydantic Settings reads from environment variables and optional .env file.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # ------------------------------------------------------------------
    # Upstream services
    # ------------------------------------------------------------------
    mekiki_ocr_path: str = Field(default="../../../../OCR")
    flowforge_server_url: str = "http://localhost:3001"
    sitemap_pro_db: str = "../../../../sitemap_pro/sitemap.db"

    # ------------------------------------------------------------------
    # AI keys
    # ------------------------------------------------------------------
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    grok_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
