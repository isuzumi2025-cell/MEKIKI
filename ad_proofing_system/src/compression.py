"""
Attachment compression service.

Provides ``compress_attachment`` – the single entry-point that
accepts a file path, detects type, and returns the path to the
compressed artefact (or raises a typed ``CompressionError``).

Supported formats:
  * JPEG / PNG  – Pillow quality reduction + optional down-scaling
  * TIFF        – convert to PNG (often smaller), then PNG pipeline
  * PDF         – pikepdf stream-level optimisation, Ghostscript fallback
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from .compression_errors import (
    CompressionError,
    CompressionErrorCode,
    ImageCompressionError,
    InputValidationError,
    PDFCompressionError,
    PostCompressionError,
    ResourceError,
)
from .config import AttachmentConfig, settings as default_settings

logger = logging.getLogger(__name__)

# ── Format helpers ────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}


def _file_size_mb(path: Path) -> float:
    """Return file size in megabytes."""
    return path.stat().st_size / (1024 * 1024)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# ── Input validation ──────────────────────────────────────────────

def _validate_input(file_path: Path, config: AttachmentConfig) -> None:
    """Run pre-flight checks on the incoming file.

    Raises ``InputValidationError`` on any problem.
    """
    logger.debug("Validating input file: %s", file_path)

    if not file_path.exists():
        raise InputValidationError(
            code=CompressionErrorCode.FILE_NOT_FOUND,
            message=f"File does not exist: {file_path}",
            details={"path": str(file_path)},
        )

    if file_path.stat().st_size == 0:
        raise InputValidationError(
            code=CompressionErrorCode.EMPTY_FILE,
            message="File is empty (0 bytes).",
            details={"path": str(file_path)},
        )

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InputValidationError(
            code=CompressionErrorCode.UNSUPPORTED_FORMAT,
            message=f"Unsupported file extension: {ext}",
            details={"path": str(file_path), "extension": ext,
                      "allowed": sorted(ALLOWED_EXTENSIONS)},
        )

    size_mb = _file_size_mb(file_path)
    if size_mb > config.MAX_SIZE_HARD_MB:
        raise InputValidationError(
            code=CompressionErrorCode.FILE_TOO_LARGE,
            message=(
                f"File size ({size_mb:.2f} MB) exceeds hard limit "
                f"({config.MAX_SIZE_HARD_MB} MB)."
            ),
            details={"size_mb": round(size_mb, 2),
                      "hard_limit_mb": config.MAX_SIZE_HARD_MB},
        )

    logger.info(
        "Input validated – %s (%.2f MB, ext=%s)",
        file_path.name, size_mb, ext,
    )


# ── Image compression ────────────────────────────────────────────

def _compress_image(
    src: Path,
    dst: Path,
    config: AttachmentConfig,
) -> Path:
    """Compress an image file (JPEG, PNG, TIFF).

    Strategy:
      1. Open with Pillow (detect corruption early).
      2. Optionally down-scale to ``IMAGE_DOWNSCALE_THRESHOLD``.
      3. For TIFF → save as PNG.
      4. Iteratively reduce JPEG quality until under soft limit.

    Returns the path of the compressed file.
    """
    logger.info("Starting image compression: %s", src.name)

    # -- 1. Open & verify ------------------------------------------------
    try:
        Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
        img = Image.open(src)
        img.load()  # force full decode – catches truncated files
    except UnidentifiedImageError as exc:
        raise ImageCompressionError(
            code=CompressionErrorCode.CORRUPTED_IMAGE,
            message=f"Cannot identify image file: {src.name}",
            details={"path": str(src)},
            original=exc,
        ) from exc
    except Image.DecompressionBombError as exc:
        raise ResourceError(
            code=CompressionErrorCode.RESOURCE_EXHAUSTION,
            message=(
                f"Image exceeds decompression-bomb limit "
                f"({config.MAX_IMAGE_PIXELS} px)."
            ),
            details={"path": str(src), "limit_px": config.MAX_IMAGE_PIXELS},
            original=exc,
        ) from exc
    except (OSError, SyntaxError) as exc:
        raise ImageCompressionError(
            code=CompressionErrorCode.IMAGE_DECODE_ERROR,
            message=f"Failed to decode image: {exc}",
            details={"path": str(src)},
            original=exc,
        ) from exc
    except MemoryError as exc:
        raise ResourceError(
            code=CompressionErrorCode.RESOURCE_EXHAUSTION,
            message="Out of memory while opening image.",
            details={"path": str(src)},
            original=exc,
        ) from exc

    logger.debug("Image opened: mode=%s, size=%s", img.mode, img.size)

    # -- 2. Down-scale if needed ----------------------------------------
    max_w, max_h = config.IMAGE_DOWNSCALE_THRESHOLD
    orig_w, orig_h = img.size
    if orig_w > max_w or orig_h > max_h:
        try:
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            logger.info(
                "Down-scaled from %dx%d to %dx%d",
                orig_w, orig_h, img.size[0], img.size[1],
            )
        except Exception as exc:
            raise ImageCompressionError(
                code=CompressionErrorCode.IMAGE_DOWNSCALE_ERROR,
                message=f"Down-scale failed: {exc}",
                details={"original_size": (orig_w, orig_h)},
                original=exc,
            ) from exc

    # -- 3. TIFF → PNG conversion ---------------------------------------
    ext = src.suffix.lower()
    if ext in {".tif", ".tiff"}:
        dst = dst.with_suffix(".png")
        logger.info("Converting TIFF to PNG: %s", dst.name)

    # -- 4. Determine output format & save ------------------------------
    out_ext = dst.suffix.lower()

    try:
        if out_ext in {".jpg", ".jpeg"}:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            # Iterative quality reduction
            quality = 85
            while quality >= config.IMAGE_QUALITY_MIN:
                img.save(dst, format="JPEG", quality=quality, optimize=True)
                if _file_size_mb(dst) <= config.MAX_SIZE_SOFT_MB:
                    break
                logger.debug(
                    "JPEG quality %d → %.2f MB (still above soft limit)",
                    quality, _file_size_mb(dst),
                )
                quality -= 10
            logger.info(
                "JPEG saved at quality=%d (%.2f MB)", quality, _file_size_mb(dst),
            )
        else:
            # PNG (or converted TIFF→PNG)
            if img.mode == "RGBA":
                img.save(dst, format="PNG", optimize=True)
            else:
                img.convert("RGB").save(dst, format="PNG", optimize=True)
            logger.info("PNG saved (%.2f MB)", _file_size_mb(dst))
    except (OSError, ValueError) as exc:
        raise ImageCompressionError(
            code=CompressionErrorCode.IMAGE_WRITE_ERROR,
            message=f"Failed to write compressed image: {exc}",
            details={"dst": str(dst)},
            original=exc,
        ) from exc
    except MemoryError as exc:
        raise ResourceError(
            code=CompressionErrorCode.RESOURCE_EXHAUSTION,
            message="Out of memory during image save.",
            details={"dst": str(dst)},
            original=exc,
        ) from exc

    return dst


# ── PDF compression ───────────────────────────────────────────────

def _compress_pdf_pikepdf(src: Path, dst: Path) -> Path:
    """Attempt lossless PDF compression via pikepdf.

    Raises ``PDFCompressionError`` on structural problems.
    """
    logger.info("Attempting pikepdf compression: %s", src.name)
    try:
        import pikepdf  # noqa: F811 – optional dep
    except ImportError as exc:
        raise PDFCompressionError(
            code=CompressionErrorCode.INVALID_PDF_STRUCTURE,
            message="pikepdf is not installed – cannot compress PDF.",
            original=exc,
        ) from exc

    try:
        pdf = pikepdf.Pdf.open(src)
    except pikepdf.PasswordError as exc:
        raise PDFCompressionError(
            code=CompressionErrorCode.PDF_ENCRYPTED,
            message="PDF is password-protected.",
            details={"path": str(src)},
            original=exc,
        ) from exc
    except pikepdf.PdfError as exc:
        raise PDFCompressionError(
            code=CompressionErrorCode.INVALID_PDF_STRUCTURE,
            message=f"Malformed PDF structure: {exc}",
            details={"path": str(src)},
            original=exc,
        ) from exc
    except MemoryError as exc:
        raise ResourceError(
            code=CompressionErrorCode.RESOURCE_EXHAUSTION,
            message="Out of memory opening PDF.",
            details={"path": str(src)},
            original=exc,
        ) from exc

    try:
        pdf.save(
            dst,
            linearize=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
        pdf.close()
    except Exception as exc:
        raise PDFCompressionError(
            code=CompressionErrorCode.PDF_WRITE_ERROR,
            message=f"Failed to write optimised PDF: {exc}",
            details={"dst": str(dst)},
            original=exc,
        ) from exc

    logger.info(
        "pikepdf compression: %.2f MB → %.2f MB",
        _file_size_mb(src), _file_size_mb(dst),
    )
    return dst


def _compress_pdf_ghostscript(
    src: Path,
    dst: Path,
    quality_profile: str,
) -> Path:
    """Lossy PDF compression via Ghostscript (``gs``).

    Raises ``PDFCompressionError`` if Ghostscript is missing or fails.
    """
    gs_bin = shutil.which("gs")
    if gs_bin is None:
        raise PDFCompressionError(
            code=CompressionErrorCode.GHOSTSCRIPT_UNAVAILABLE,
            message="Ghostscript (gs) is not installed on this system.",
        )

    cmd = [
        gs_bin,
        "-sDEVICE=pdfwrite",
        f"-dPDFSETTINGS=/{quality_profile}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={dst}",
        str(src),
    ]

    logger.info("Running Ghostscript: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise ResourceError(
            code=CompressionErrorCode.TIMEOUT,
            message="Ghostscript timed out after 120 s.",
            details={"cmd": cmd},
            original=exc,
        ) from exc
    except OSError as exc:
        raise PDFCompressionError(
            code=CompressionErrorCode.GHOSTSCRIPT_FAILED,
            message=f"Failed to launch Ghostscript: {exc}",
            details={"cmd": cmd},
            original=exc,
        ) from exc

    if result.returncode != 0:
        raise PDFCompressionError(
            code=CompressionErrorCode.GHOSTSCRIPT_FAILED,
            message=f"Ghostscript exited with code {result.returncode}.",
            details={
                "returncode": result.returncode,
                "stderr": result.stderr[:2000],
            },
        )

    if not dst.exists() or dst.stat().st_size == 0:
        raise PDFCompressionError(
            code=CompressionErrorCode.PDF_WRITE_ERROR,
            message="Ghostscript produced an empty output file.",
            details={"dst": str(dst)},
        )

    logger.info(
        "Ghostscript compression: %.2f MB → %.2f MB",
        _file_size_mb(src), _file_size_mb(dst),
    )
    return dst


def _compress_pdf(src: Path, dst: Path, config: AttachmentConfig) -> Path:
    """Compress a PDF file.

    1. Try pikepdf (lossless).
    2. If still above soft limit, try Ghostscript (lossy).
    """
    logger.info("Starting PDF compression pipeline: %s", src.name)

    # -- Step 1: pikepdf --
    pikepdf_dst = dst.with_name(dst.stem + "_pike.pdf")
    try:
        _compress_pdf_pikepdf(src, pikepdf_dst)
    except PDFCompressionError:
        logger.warning(
            "pikepdf compression failed – falling through to Ghostscript.",
            exc_info=True,
        )
        pikepdf_dst = None

    if pikepdf_dst and pikepdf_dst.exists():
        if _file_size_mb(pikepdf_dst) <= config.MAX_SIZE_SOFT_MB:
            shutil.move(str(pikepdf_dst), str(dst))
            return dst
        logger.info(
            "pikepdf result still %.2f MB (soft limit %d MB) – trying Ghostscript.",
            _file_size_mb(pikepdf_dst), config.MAX_SIZE_SOFT_MB,
        )
        # Use pikepdf output as Ghostscript input (already partially optimised).
        gs_src = pikepdf_dst
    else:
        gs_src = src

    # -- Step 2: Ghostscript --
    gs_dst = dst.with_name(dst.stem + "_gs.pdf")
    _compress_pdf_ghostscript(gs_src, gs_dst, config.PDF_QUALITY_PROFILE)

    shutil.move(str(gs_dst), str(dst))

    # Clean up pikepdf temp if it exists
    if pikepdf_dst and pikepdf_dst.exists():
        pikepdf_dst.unlink(missing_ok=True)

    return dst


# ── Post-compression check ────────────────────────────────────────

def _post_compression_check(
    dst: Path,
    config: AttachmentConfig,
) -> None:
    """Verify the compressed file is within limits.

    Raises ``PostCompressionError`` if the file is still too large.
    """
    if not dst.exists():
        raise PostCompressionError(
            code=CompressionErrorCode.OUTPUT_CORRUPTED,
            message="Compressed output file does not exist.",
            details={"dst": str(dst)},
        )

    size_mb = _file_size_mb(dst)
    if size_mb > config.MAX_SIZE_HARD_MB:
        raise PostCompressionError(
            code=CompressionErrorCode.STILL_TOO_LARGE,
            message=(
                f"Compressed file ({size_mb:.2f} MB) still exceeds hard limit "
                f"({config.MAX_SIZE_HARD_MB} MB). Consider a smaller source file."
            ),
            details={"size_mb": round(size_mb, 2),
                      "hard_limit_mb": config.MAX_SIZE_HARD_MB},
        )

    logger.info("Post-compression check passed: %.2f MB", size_mb)


# ── Public API ────────────────────────────────────────────────────

def compress_attachment(
    file_path: str | Path,
    config: Optional[AttachmentConfig] = None,
    output_dir: Optional[str | Path] = None,
) -> Path:
    """Compress an attachment file and return the path to the result.

    Parameters
    ----------
    file_path : str | Path
        Path to the source file.
    config : AttachmentConfig, optional
        Override the default configuration.
    output_dir : str | Path, optional
        Directory to write the compressed file into.  Defaults to
        ``config.TMP_DIR``.

    Returns
    -------
    Path
        Path to the compressed artefact.

    Raises
    ------
    CompressionError
        Any subclass – always with a ``code`` attribute carrying the
        machine-readable ``CompressionErrorCode``.
    """
    config = config or default_settings
    src = Path(file_path)

    logger.info(
        "compress_attachment called: file=%s, hard_limit=%d MB, soft_limit=%d MB",
        src.name, config.MAX_SIZE_HARD_MB, config.MAX_SIZE_SOFT_MB,
    )

    # ── 1. Validate input ─────────────────────────────────────────
    _validate_input(src, config)

    # ── 2. Decide if compression is needed ────────────────────────
    size_mb = _file_size_mb(src)
    if size_mb <= config.MAX_SIZE_SOFT_MB:
        logger.info(
            "File (%.2f MB) is within soft limit – no compression needed.",
            size_mb,
        )
        return src  # already small enough

    # ── 3. Prepare output path ────────────────────────────────────
    out_dir = Path(output_dir) if output_dir else Path(config.TMP_DIR)
    _ensure_dir(out_dir)
    dst = out_dir / (src.stem + "_compressed" + src.suffix)

    ext = src.suffix.lower()

    try:
        # ── 4. Compress ──────────────────────────────────────────
        if ext in IMAGE_EXTENSIONS:
            dst = _compress_image(src, dst, config)
        elif ext in PDF_EXTENSIONS:
            dst = _compress_pdf(src, dst, config)
        else:
            # Should never reach here after validation, but be safe.
            raise InputValidationError(
                code=CompressionErrorCode.UNSUPPORTED_FORMAT,
                message=f"No compression handler for extension: {ext}",
                details={"extension": ext},
            )

        # ── 5. Post-compression check ────────────────────────────
        _post_compression_check(dst, config)

    except CompressionError:
        # Already a typed error – let it bubble.
        logger.error("Compression failed.", exc_info=True)
        raise
    except MemoryError as exc:
        logger.critical("Memory exhaustion during compression.", exc_info=True)
        raise ResourceError(
            code=CompressionErrorCode.RESOURCE_EXHAUSTION,
            message="Out of memory during compression.",
            details={"path": str(src)},
            original=exc,
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during compression.")
        raise CompressionError(
            code=CompressionErrorCode.UNEXPECTED_ERROR,
            message=f"Unexpected error: {exc}",
            details={"path": str(src), "type": type(exc).__name__},
            original=exc,
        ) from exc

    logger.info(
        "Compression complete: %s → %s (%.2f MB → %.2f MB)",
        src.name, dst.name, size_mb, _file_size_mb(dst),
    )
    return dst
