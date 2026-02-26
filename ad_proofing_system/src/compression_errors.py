"""
Compression error codes and custom exception hierarchy.

Every failure in the compression pipeline is wrapped in a typed
exception carrying a machine-readable ``CompressionErrorCode``,
a human-friendly message, and an optional detail dict for structured
logging / API responses.
"""

from __future__ import annotations

import enum
from typing import Any, Dict, Optional


# ── Error codes ───────────────────────────────────────────────────
class CompressionErrorCode(enum.Enum):
    """Machine-readable error codes for compression failures."""

    # Input validation (1xx)
    UNSUPPORTED_FORMAT = "COMP-100"
    FILE_TOO_LARGE = "COMP-101"
    EMPTY_FILE = "COMP-102"
    FILE_NOT_FOUND = "COMP-103"

    # Image-specific (2xx)
    CORRUPTED_IMAGE = "COMP-200"
    IMAGE_DECODE_ERROR = "COMP-201"
    IMAGE_WRITE_ERROR = "COMP-202"
    IMAGE_DOWNSCALE_ERROR = "COMP-203"

    # PDF-specific (3xx)
    INVALID_PDF_STRUCTURE = "COMP-300"
    PDF_ENCRYPTED = "COMP-301"
    PDF_PAGE_ERROR = "COMP-302"
    PDF_WRITE_ERROR = "COMP-303"
    GHOSTSCRIPT_UNAVAILABLE = "COMP-310"
    GHOSTSCRIPT_FAILED = "COMP-311"

    # Post-compression (4xx)
    STILL_TOO_LARGE = "COMP-400"
    OUTPUT_CORRUPTED = "COMP-401"

    # System / resource (5xx)
    RESOURCE_EXHAUSTION = "COMP-500"
    TIMEOUT = "COMP-501"
    IO_ERROR = "COMP-502"
    UNEXPECTED_ERROR = "COMP-599"


# ── Exception hierarchy ──────────────────────────────────────────

class CompressionError(Exception):
    """Base exception for the attachment compression pipeline.

    Attributes
    ----------
    code : CompressionErrorCode
        Machine-readable error code.
    message : str
        Human-readable description.
    details : dict
        Arbitrary structured data for debugging / API responses.
    original : Exception | None
        The wrapped lower-level exception, if any.
    """

    def __init__(
        self,
        code: CompressionErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original: Optional[Exception] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.original = original
        super().__init__(f"[{code.value}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for JSON API responses."""
        result: Dict[str, Any] = {
            "error_code": self.code.value,
            "error_name": self.code.name,
            "message": self.message,
            "details": self.details,
        }
        if self.original is not None:
            result["original_error"] = str(self.original)
        return result


class InputValidationError(CompressionError):
    """Raised when the incoming file fails pre-flight checks."""


class ImageCompressionError(CompressionError):
    """Raised when image-specific compression fails."""


class PDFCompressionError(CompressionError):
    """Raised when PDF-specific compression fails."""


class PostCompressionError(CompressionError):
    """Raised after compression when the result still violates limits."""


class ResourceError(CompressionError):
    """Raised on system-level resource problems (OOM, timeout, I/O)."""
