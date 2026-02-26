"""
Attachment compression configuration.

Provides a Pydantic-based settings class for controlling attachment
size limits, compression quality, and storage paths.
"""

from __future__ import annotations

import os
from typing import Tuple

from pydantic import Field
from pydantic_settings import BaseSettings


class AttachmentConfig(BaseSettings):
    """Configuration for the attachment compression pipeline."""

    # ── Size limits (MB) ──────────────────────────────────────────
    MAX_SIZE_HARD_MB: int = Field(
        default=25,
        description="Absolute upper bound – files above this are always rejected.",
    )
    MAX_SIZE_SOFT_MB: int = Field(
        default=15,
        description="Files above this trigger automatic compression.",
    )

    # ── Image quality ─────────────────────────────────────────────
    IMAGE_QUALITY_MIN: int = Field(
        default=35,
        ge=1,
        le=100,
        description="JPEG quality floor during iterative compression.",
    )
    IMAGE_DOWNSCALE_THRESHOLD: Tuple[int, int] = Field(
        default=(3500, 3500),
        description="Max (width, height) in px before downscaling.",
    )

    # ── PDF quality ───────────────────────────────────────────────
    PDF_QUALITY_PROFILE: str = Field(
        default="screen",
        description="Ghostscript quality preset (screen | ebook | printer | prepress).",
    )

    # ── Paths ─────────────────────────────────────────────────────
    TMP_DIR: str = Field(
        default=os.path.join("/tmp", "mekiki", "attachments"),
        description="Temporary directory for in-flight files.",
    )
    STORAGE_BUCKET: str = Field(
        default="mekiki-attachments",
        description="Target storage bucket / container name.",
    )

    # ── Resource limits ───────────────────────────────────────────
    MAX_IMAGE_PIXELS: int = Field(
        default=178_956_970,
        description="Pillow decompression-bomb guard (default ~179 MP).",
    )
    COMPRESSION_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="Maximum wall-clock time for a single compression job.",
    )

    model_config = {"env_prefix": "MEKIKI_ATTACH_"}


# Module-level singleton – importable everywhere.
settings = AttachmentConfig()
