"""
FastAPI upload endpoint for the MEKIKI attachment pipeline.

Validates incoming files, triggers the compression workflow, and
returns structured JSON responses – including typed error codes on
failure.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .compression import compress_attachment
from .compression_errors import CompressionError
from .config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

app = FastAPI(title="MEKIKI Attachment Service")


def _ext_ok(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


@app.post("/attachments")
async def upload_attachment(file: UploadFile = File(...)) -> JSONResponse:
    """Accept an attachment, compress if needed, and persist.

    Returns
    -------
    JSONResponse
        On success: ``{"status": "ok", "path": ..., "size_mb": ...}``
        On failure: ``{"status": "error", "error_code": ..., ...}``
    """
    filename = file.filename or "unknown"
    logger.info("Received upload: %s (content_type=%s)", filename, file.content_type)

    # ── 1. Extension check ────────────────────────────────────────
    if not _ext_ok(filename):
        logger.warning("Rejected upload – unsupported extension: %s", filename)
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "COMP-100",
                "message": f"Unsupported file type: {Path(filename).suffix}",
            },
        )

    # ── 2. Persist to temp ────────────────────────────────────────
    tmp_dir = Path(settings.TMP_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4()}{Path(filename).suffix}"

    try:
        with tmp_path.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)
    except OSError as exc:
        logger.error("Failed to write temp file: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "COMP-502",
                "message": f"I/O error writing temp file: {exc}",
            },
        ) from exc

    raw_size = _file_size_mb(tmp_path)
    logger.info("Temp file written: %s (%.2f MB)", tmp_path.name, raw_size)

    # ── 3. Hard-limit gate ────────────────────────────────────────
    if raw_size > settings.MAX_SIZE_HARD_MB:
        tmp_path.unlink(missing_ok=True)
        logger.warning(
            "Rejected upload – exceeds hard limit: %.2f MB > %d MB",
            raw_size, settings.MAX_SIZE_HARD_MB,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "COMP-101",
                "message": (
                    f"File size ({raw_size:.2f} MB) exceeds maximum "
                    f"allowed ({settings.MAX_SIZE_HARD_MB} MB)."
                ),
            },
        )

    # ── 4. Compress ───────────────────────────────────────────────
    try:
        compressed = compress_attachment(tmp_path, settings)
    except CompressionError as exc:
        logger.error(
            "Compression error [%s]: %s", exc.code.value, exc.message,
            exc_info=True,
        )
        # Clean up temp
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=exc.to_dict(),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during compression.")
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "COMP-599",
                "message": f"Unexpected server error: {exc}",
            },
        ) from exc

    final_size = _file_size_mb(compressed)
    logger.info(
        "Upload processed: %s → %s (%.2f MB → %.2f MB)",
        filename, compressed.name, raw_size, final_size,
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "original_name": filename,
            "compressed_path": str(compressed),
            "original_size_mb": round(raw_size, 2),
            "compressed_size_mb": round(final_size, 2),
        },
    )
