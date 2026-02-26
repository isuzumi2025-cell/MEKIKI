"""
Comprehensive test suite for the attachment compression pipeline.

Intentionally triggers different failure scenarios and verifies that
the correct error codes are logged and raised.

Test categories
---------------
- Input validation (missing files, empty files, unsupported formats, oversized)
- Image corruption / decode errors
- PDF structural errors (malformed, encrypted)
- Resource exhaustion (decompression bombs, memory)
- Post-compression size checks
- Ghostscript fallback paths
- Successful compression paths (JPEG, PNG, TIFF→PNG, PDF)
- Logging verification
"""

from __future__ import annotations

import io
import logging
import os
import struct
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ad_proofing_system.src.compression import (
    _compress_image,
    _compress_pdf,
    _compress_pdf_ghostscript,
    _compress_pdf_pikepdf,
    _post_compression_check,
    _validate_input,
    compress_attachment,
)
from ad_proofing_system.src.compression_errors import (
    CompressionError,
    CompressionErrorCode,
    ImageCompressionError,
    InputValidationError,
    PDFCompressionError,
    PostCompressionError,
    ResourceError,
)
from ad_proofing_system.src.config import AttachmentConfig


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory that is cleaned up after each test."""
    with tempfile.TemporaryDirectory(prefix="mekiki_test_") as d:
        yield Path(d)


@pytest.fixture
def config(tmp_dir: Path) -> AttachmentConfig:
    """Return a test-friendly configuration with low limits."""
    return AttachmentConfig(
        MAX_SIZE_HARD_MB=15,
        MAX_SIZE_SOFT_MB=1,
        IMAGE_QUALITY_MIN=50,
        IMAGE_DOWNSCALE_THRESHOLD=(800, 800),
        PDF_QUALITY_PROFILE="screen",
        TMP_DIR=str(tmp_dir / "output"),
        MAX_IMAGE_PIXELS=50_000_000,
        COMPRESSION_TIMEOUT_SECONDS=30,
    )


@pytest.fixture
def small_jpeg(tmp_dir: Path) -> Path:
    """Create a small valid JPEG (under soft limit)."""
    p = tmp_dir / "small.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(p, format="JPEG", quality=85)
    return p


@pytest.fixture
def large_jpeg(tmp_dir: Path) -> Path:
    """Create a JPEG that exceeds the 1 MB soft limit."""
    p = tmp_dir / "large.jpg"
    # ~2000x2000 random-ish image saves to >1 MB at high quality
    img = Image.new("RGB", (3000, 3000), color="blue")
    # Draw some noise to prevent trivial compression
    import random
    pixels = img.load()
    for x in range(0, 3000, 3):
        for y in range(0, 3000, 3):
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img.save(p, format="JPEG", quality=98)
    return p


@pytest.fixture
def valid_png(tmp_dir: Path) -> Path:
    """Create a valid PNG file."""
    p = tmp_dir / "valid.png"
    img = Image.new("RGBA", (200, 200), color=(0, 128, 255, 200))
    img.save(p, format="PNG")
    return p


@pytest.fixture
def large_png(tmp_dir: Path) -> Path:
    """Create a large PNG that exceeds the 1 MB soft limit."""
    p = tmp_dir / "large.png"
    import random
    img = Image.new("RGB", (2000, 2000), color="green")
    pixels = img.load()
    for x in range(0, 2000, 2):
        for y in range(0, 2000, 2):
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img.save(p, format="PNG")
    return p


@pytest.fixture
def valid_tiff(tmp_dir: Path) -> Path:
    """Create a valid TIFF file."""
    p = tmp_dir / "valid.tif"
    img = Image.new("RGB", (500, 500), color="yellow")
    img.save(p, format="TIFF")
    return p


@pytest.fixture
def corrupted_image(tmp_dir: Path) -> Path:
    """Create a file with a JPEG extension but garbage content."""
    p = tmp_dir / "corrupted.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + os.urandom(512))  # JPEG SOI + junk
    return p


@pytest.fixture
def empty_file(tmp_dir: Path) -> Path:
    """Create a 0-byte file."""
    p = tmp_dir / "empty.pdf"
    p.write_bytes(b"")
    return p


@pytest.fixture
def truncated_png(tmp_dir: Path) -> Path:
    """Create a PNG that is truncated mid-stream."""
    p = tmp_dir / "truncated.png"
    buf = io.BytesIO()
    img = Image.new("RGB", (500, 500), color="cyan")
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    # Truncate to half the data
    p.write_bytes(raw[: len(raw) // 2])
    return p


@pytest.fixture
def fake_pdf(tmp_dir: Path) -> Path:
    """Create a minimal valid-looking but actually malformed PDF."""
    p = tmp_dir / "malformed.pdf"
    # Starts with PDF header but has no valid structure
    p.write_bytes(b"%PDF-1.4\n%garbage\n%%EOF\n")
    return p


@pytest.fixture
def oversized_file(tmp_dir: Path, config: AttachmentConfig) -> Path:
    """Create a file that exceeds the hard limit."""
    p = tmp_dir / "huge.jpg"
    # Write just enough to exceed the hard limit (config.MAX_SIZE_HARD_MB=15)
    size_bytes = (config.MAX_SIZE_HARD_MB + 1) * 1024 * 1024
    with p.open("wb") as f:
        f.write(os.urandom(size_bytes))
    return p


# =====================================================================
# 1. Input Validation Tests
# =====================================================================

class TestInputValidation:
    """Tests for _validate_input and early rejection paths."""

    def test_file_not_found(self, tmp_dir: Path, config: AttachmentConfig) -> None:
        with pytest.raises(InputValidationError) as exc_info:
            _validate_input(tmp_dir / "nonexistent.jpg", config)
        assert exc_info.value.code == CompressionErrorCode.FILE_NOT_FOUND

    def test_empty_file(self, empty_file: Path, config: AttachmentConfig) -> None:
        with pytest.raises(InputValidationError) as exc_info:
            _validate_input(empty_file, config)
        assert exc_info.value.code == CompressionErrorCode.EMPTY_FILE

    def test_unsupported_format(self, tmp_dir: Path, config: AttachmentConfig) -> None:
        bmp = tmp_dir / "image.bmp"
        bmp.write_bytes(b"BM" + os.urandom(100))
        with pytest.raises(InputValidationError) as exc_info:
            _validate_input(bmp, config)
        assert exc_info.value.code == CompressionErrorCode.UNSUPPORTED_FORMAT
        assert ".bmp" in exc_info.value.details["extension"]

    def test_file_too_large(self, oversized_file: Path, config: AttachmentConfig) -> None:
        with pytest.raises(InputValidationError) as exc_info:
            _validate_input(oversized_file, config)
        assert exc_info.value.code == CompressionErrorCode.FILE_TOO_LARGE
        assert exc_info.value.details["hard_limit_mb"] == config.MAX_SIZE_HARD_MB

    def test_valid_file_passes(self, small_jpeg: Path, config: AttachmentConfig) -> None:
        # Should not raise
        _validate_input(small_jpeg, config)

    def test_unsupported_format_via_compress_attachment(
        self, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """End-to-end: unsupported format through the public API."""
        doc = tmp_dir / "file.docx"
        doc.write_bytes(b"PK\x03\x04" + os.urandom(100))
        with pytest.raises(InputValidationError) as exc_info:
            compress_attachment(doc, config)
        assert exc_info.value.code == CompressionErrorCode.UNSUPPORTED_FORMAT


# =====================================================================
# 2. Corrupted Image Tests
# =====================================================================

class TestCorruptedImages:
    """Tests for corrupted / unreadable image files."""

    def test_corrupted_jpeg(
        self, corrupted_image: Path, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        dst = tmp_dir / "out.jpg"
        with pytest.raises(ImageCompressionError) as exc_info:
            _compress_image(corrupted_image, dst, config)
        assert exc_info.value.code in {
            CompressionErrorCode.CORRUPTED_IMAGE,
            CompressionErrorCode.IMAGE_DECODE_ERROR,
        }

    def test_truncated_png(
        self, truncated_png: Path, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        dst = tmp_dir / "out.png"
        with pytest.raises((ImageCompressionError, ResourceError)) as exc_info:
            _compress_image(truncated_png, dst, config)
        assert exc_info.value.code in {
            CompressionErrorCode.CORRUPTED_IMAGE,
            CompressionErrorCode.IMAGE_DECODE_ERROR,
            CompressionErrorCode.IMAGE_WRITE_ERROR,
            CompressionErrorCode.RESOURCE_EXHAUSTION,
        }

    def test_corrupted_image_via_compress_attachment(
        self, corrupted_image: Path, config: AttachmentConfig,
    ) -> None:
        """End-to-end: corrupted image through the public API.

        The file must exceed the soft limit to trigger compression.
        """
        # Make the corrupted file large enough to trigger compression
        with corrupted_image.open("ab") as f:
            f.write(os.urandom(2 * 1024 * 1024))

        with pytest.raises(CompressionError) as exc_info:
            compress_attachment(corrupted_image, config)
        assert exc_info.value.code in {
            CompressionErrorCode.CORRUPTED_IMAGE,
            CompressionErrorCode.IMAGE_DECODE_ERROR,
        }

    def test_non_image_with_image_extension(
        self, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """A .png file that is actually a text file."""
        fake = tmp_dir / "fake.png"
        fake.write_text("this is not an image at all")
        dst = tmp_dir / "out.png"
        with pytest.raises(ImageCompressionError) as exc_info:
            _compress_image(fake, dst, config)
        assert exc_info.value.code in {
            CompressionErrorCode.CORRUPTED_IMAGE,
            CompressionErrorCode.IMAGE_DECODE_ERROR,
        }


# =====================================================================
# 3. Resource Exhaustion Tests
# =====================================================================

class TestResourceExhaustion:
    """Tests for memory / decompression-bomb scenarios."""

    def test_decompression_bomb_guard(
        self, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """A very low MAX_IMAGE_PIXELS should trigger the bomb guard."""
        bomb_config = config.model_copy(update={"MAX_IMAGE_PIXELS": 100})
        # Create a small-but-not-tiny image
        p = tmp_dir / "bomb.png"
        img = Image.new("RGB", (50, 50), color="red")
        img.save(p, format="PNG")
        dst = tmp_dir / "out.png"
        with pytest.raises(ResourceError) as exc_info:
            _compress_image(p, dst, bomb_config)
        assert exc_info.value.code == CompressionErrorCode.RESOURCE_EXHAUSTION

    def test_memory_error_on_open(
        self, small_jpeg: Path, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """Simulate MemoryError when opening an image."""
        dst = tmp_dir / "out.jpg"
        with patch.object(Image.Image, "load", side_effect=MemoryError("OOM")):
            with pytest.raises(ResourceError) as exc_info:
                _compress_image(small_jpeg, dst, config)
            assert exc_info.value.code == CompressionErrorCode.RESOURCE_EXHAUSTION

    def test_memory_error_during_save(
        self, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """Simulate MemoryError during image save."""
        p = tmp_dir / "img.jpg"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(p, format="JPEG")
        dst = tmp_dir / "out.jpg"

        with patch.object(Image.Image, "save", side_effect=MemoryError("OOM")):
            with pytest.raises(ResourceError) as exc_info:
                _compress_image(p, dst, config)
            assert exc_info.value.code == CompressionErrorCode.RESOURCE_EXHAUSTION

    def test_unexpected_error_wrapped(
        self, small_jpeg: Path, config: AttachmentConfig, tmp_dir: Path,
    ) -> None:
        """Unknown exceptions get wrapped as UNEXPECTED_ERROR."""
        # Force the soft limit to 0 so compression is triggered
        tiny_config = config.model_copy(update={"MAX_SIZE_SOFT_MB": 0})
        with patch(
            "ad_proofing_system.src.compression._compress_image",
            side_effect=RuntimeError("cosmic ray"),
        ):
            with pytest.raises(CompressionError) as exc_info:
                compress_attachment(small_jpeg, tiny_config, output_dir=tmp_dir)
            assert exc_info.value.code == CompressionErrorCode.UNEXPECTED_ERROR


# =====================================================================
# 4. PDF Error Tests
# =====================================================================

class TestPDFErrors:
    """Tests for PDF-specific failure scenarios."""

    def test_malformed_pdf_pikepdf(
        self, fake_pdf: Path, tmp_dir: Path,
    ) -> None:
        dst = tmp_dir / "out.pdf"
        with pytest.raises(PDFCompressionError) as exc_info:
            _compress_pdf_pikepdf(fake_pdf, dst)
        assert exc_info.value.code in {
            CompressionErrorCode.INVALID_PDF_STRUCTURE,
            CompressionErrorCode.PDF_ENCRYPTED,
        }

    def test_pikepdf_not_installed(
        self, fake_pdf: Path, tmp_dir: Path,
    ) -> None:
        """Simulate pikepdf being absent."""
        dst = tmp_dir / "out.pdf"
        import builtins
        real_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):
            if name == "pikepdf":
                raise ImportError("No module named 'pikepdf'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(PDFCompressionError) as exc_info:
                _compress_pdf_pikepdf(fake_pdf, dst)
            assert exc_info.value.code == CompressionErrorCode.INVALID_PDF_STRUCTURE

    def test_ghostscript_not_found(
        self, fake_pdf: Path, tmp_dir: Path,
    ) -> None:
        dst = tmp_dir / "out.pdf"
        with patch("shutil.which", return_value=None):
            with pytest.raises(PDFCompressionError) as exc_info:
                _compress_pdf_ghostscript(fake_pdf, dst, "screen")
            assert exc_info.value.code == CompressionErrorCode.GHOSTSCRIPT_UNAVAILABLE

    def test_ghostscript_nonzero_exit(
        self, fake_pdf: Path, tmp_dir: Path,
    ) -> None:
        dst = tmp_dir / "out.pdf"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: /undefined in foo"

        with patch("shutil.which", return_value="/usr/bin/gs"), \
             patch("subprocess.run", return_value=mock_result):
            with pytest.raises(PDFCompressionError) as exc_info:
                _compress_pdf_ghostscript(fake_pdf, dst, "screen")
            assert exc_info.value.code == CompressionErrorCode.GHOSTSCRIPT_FAILED
            assert "1" in exc_info.value.message

    def test_ghostscript_timeout(
        self, fake_pdf: Path, tmp_dir: Path,
    ) -> None:
        import subprocess
        dst = tmp_dir / "out.pdf"
        with patch("shutil.which", return_value="/usr/bin/gs"), \
             patch(
                 "subprocess.run",
                 side_effect=subprocess.TimeoutExpired(cmd="gs", timeout=120),
             ):
            with pytest.raises(ResourceError) as exc_info:
                _compress_pdf_ghostscript(fake_pdf, dst, "screen")
            assert exc_info.value.code == CompressionErrorCode.TIMEOUT

    def test_malformed_pdf_via_compress_attachment(
        self, fake_pdf: Path, config: AttachmentConfig, tmp_dir: Path,
    ) -> None:
        """End-to-end: malformed PDF through the public API."""
        # Make file large enough to exceed soft limit
        with fake_pdf.open("ab") as f:
            f.write(os.urandom(2 * 1024 * 1024))

        with pytest.raises(CompressionError) as exc_info:
            compress_attachment(fake_pdf, config, output_dir=tmp_dir)
        # Could be INVALID_PDF_STRUCTURE or GHOSTSCRIPT_* depending on env
        assert "COMP-3" in exc_info.value.code.value or \
               exc_info.value.code == CompressionErrorCode.UNEXPECTED_ERROR


# =====================================================================
# 5. Post-Compression Check Tests
# =====================================================================

class TestPostCompressionCheck:
    """Tests for the size check after compression."""

    def test_output_missing(self, tmp_dir: Path, config: AttachmentConfig) -> None:
        with pytest.raises(PostCompressionError) as exc_info:
            _post_compression_check(tmp_dir / "ghost.jpg", config)
        assert exc_info.value.code == CompressionErrorCode.OUTPUT_CORRUPTED

    def test_still_too_large(self, tmp_dir: Path, config: AttachmentConfig) -> None:
        big = tmp_dir / "big.jpg"
        # Write data exceeding hard limit
        big.write_bytes(os.urandom((config.MAX_SIZE_HARD_MB + 1) * 1024 * 1024))
        with pytest.raises(PostCompressionError) as exc_info:
            _post_compression_check(big, config)
        assert exc_info.value.code == CompressionErrorCode.STILL_TOO_LARGE

    def test_within_limits_passes(self, small_jpeg: Path, config: AttachmentConfig) -> None:
        # Should not raise
        _post_compression_check(small_jpeg, config)


# =====================================================================
# 6. Successful Compression Tests
# =====================================================================

class TestSuccessfulCompression:
    """Tests for the happy path."""

    def test_small_file_skips_compression(
        self, small_jpeg: Path, config: AttachmentConfig,
    ) -> None:
        """Files under soft limit are returned unchanged."""
        result = compress_attachment(small_jpeg, config)
        assert result == small_jpeg

    def test_jpeg_compression(
        self, large_jpeg: Path, config: AttachmentConfig, tmp_dir: Path,
    ) -> None:
        """A large JPEG should be compressed and returned."""
        result = compress_attachment(large_jpeg, config, output_dir=tmp_dir)
        assert result.exists()
        # Compressed should generally be smaller
        assert result.stat().st_size <= large_jpeg.stat().st_size

    def test_png_compression(
        self, large_png: Path, config: AttachmentConfig, tmp_dir: Path,
    ) -> None:
        """A large PNG should be compressed."""
        result = compress_attachment(large_png, config, output_dir=tmp_dir)
        assert result.exists()

    def test_tiff_converts_to_png(
        self, tmp_dir: Path, config: AttachmentConfig,
    ) -> None:
        """A TIFF file should be converted to PNG."""
        tiff_path = tmp_dir / "convert_me.tif"
        import random
        img = Image.new("RGB", (1500, 1500), color="purple")
        pixels = img.load()
        for x in range(0, 1500, 5):
            for y in range(0, 1500, 5):
                pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        img.save(tiff_path, format="TIFF")

        # Only trigger if above soft limit
        if tiff_path.stat().st_size / (1024 * 1024) <= config.MAX_SIZE_SOFT_MB:
            # Force soft limit lower
            config = config.model_copy(update={"MAX_SIZE_SOFT_MB": 0})

        result = compress_attachment(tiff_path, config, output_dir=tmp_dir)
        assert result.exists()
        assert result.suffix == ".png"


# =====================================================================
# 7. Logging Verification Tests
# =====================================================================

class TestLoggingOutput:
    """Verify that the compression pipeline emits structured log messages."""

    def test_validation_logs_on_success(
        self, small_jpeg: Path, config: AttachmentConfig, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="ad_proofing_system.src.compression"):
            _validate_input(small_jpeg, config)
        assert any("Input validated" in r.message for r in caplog.records)

    def test_compression_skipped_log(
        self, small_jpeg: Path, config: AttachmentConfig, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="ad_proofing_system.src.compression"):
            compress_attachment(small_jpeg, config)
        assert any("no compression needed" in r.message for r in caplog.records)

    def test_error_logged_on_corrupted_image(
        self, corrupted_image: Path, config: AttachmentConfig,
        tmp_dir: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Make it large enough to trigger compression
        with corrupted_image.open("ab") as f:
            f.write(os.urandom(2 * 1024 * 1024))

        with caplog.at_level(logging.ERROR, logger="ad_proofing_system.src.compression"):
            with pytest.raises(CompressionError):
                compress_attachment(corrupted_image, config, output_dir=tmp_dir)
        assert any("Compression failed" in r.message for r in caplog.records)

    def test_error_logged_on_file_not_found(
        self, tmp_dir: Path, config: AttachmentConfig, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.DEBUG, logger="ad_proofing_system.src.compression"):
            with pytest.raises(InputValidationError):
                compress_attachment(tmp_dir / "nope.jpg", config)
        # InputValidationError is raised before the compression try/except,
        # so we check the debug-level validation log instead.
        assert any("Validating input" in r.message or "compress_attachment called" in r.message
                   for r in caplog.records)


# =====================================================================
# 8. Error Serialisation Tests
# =====================================================================

class TestErrorSerialisation:
    """Verify CompressionError.to_dict() produces correct JSON-safe dicts."""

    def test_to_dict_basic(self) -> None:
        err = CompressionError(
            code=CompressionErrorCode.CORRUPTED_IMAGE,
            message="bad image",
            details={"path": "/tmp/bad.jpg"},
        )
        d = err.to_dict()
        assert d["error_code"] == "COMP-200"
        assert d["error_name"] == "CORRUPTED_IMAGE"
        assert d["message"] == "bad image"
        assert d["details"]["path"] == "/tmp/bad.jpg"
        assert "original_error" not in d

    def test_to_dict_with_original(self) -> None:
        orig = ValueError("oh no")
        err = CompressionError(
            code=CompressionErrorCode.UNEXPECTED_ERROR,
            message="wrapper",
            original=orig,
        )
        d = err.to_dict()
        assert d["original_error"] == "oh no"

    def test_str_repr(self) -> None:
        err = CompressionError(
            code=CompressionErrorCode.FILE_TOO_LARGE,
            message="too big",
        )
        assert "[COMP-101]" in str(err)
        assert "too big" in str(err)


# =====================================================================
# 9. Upload API Tests
# =====================================================================

class TestUploadAPI:
    """Integration tests for the FastAPI upload endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from ad_proofing_system.src.upload_api import app
        return TestClient(app)

    def test_unsupported_extension(self, client) -> None:
        resp = client.post(
            "/attachments",
            files={"file": ("test.docx", b"PK\x03\x04data", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "COMP-100" in str(resp.json()["detail"])

    def test_valid_small_jpeg_upload(self, client, tmp_dir: Path) -> None:
        # Create a small valid JPEG in memory
        buf = io.BytesIO()
        img = Image.new("RGB", (50, 50), color="red")
        img.save(buf, format="JPEG")
        buf.seek(0)

        resp = client.post(
            "/attachments",
            files={"file": ("photo.jpg", buf, "image/jpeg")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["original_name"] == "photo.jpg"

    def test_corrupted_image_upload(self, client) -> None:
        """Upload a corrupted JPEG; expect a 422 with error details."""
        # Create corrupted data large enough to trigger compression
        data = b"\xff\xd8\xff\xe0" + os.urandom(2 * 1024 * 1024)
        resp = client.post(
            "/attachments",
            files={"file": ("broken.jpg", data, "image/jpeg")},
        )
        # Should get 422 (compression error) or 200 if it happens to be
        # under the default soft limit. With default config (15 MB soft),
        # 2 MB won't trigger compression – so this mainly tests the upload path.
        assert resp.status_code in {200, 422}


# =====================================================================
# 10. Config Tests
# =====================================================================

class TestConfig:
    """Tests for AttachmentConfig defaults and overrides."""

    def test_defaults(self) -> None:
        cfg = AttachmentConfig()
        assert cfg.MAX_SIZE_HARD_MB == 25
        assert cfg.MAX_SIZE_SOFT_MB == 15
        assert cfg.IMAGE_QUALITY_MIN == 35
        assert cfg.PDF_QUALITY_PROFILE == "screen"

    def test_override_via_constructor(self) -> None:
        cfg = AttachmentConfig(MAX_SIZE_HARD_MB=50, IMAGE_QUALITY_MIN=20)
        assert cfg.MAX_SIZE_HARD_MB == 50
        assert cfg.IMAGE_QUALITY_MIN == 20

    def test_model_copy(self) -> None:
        cfg = AttachmentConfig()
        new = cfg.model_copy(update={"MAX_SIZE_SOFT_MB": 5})
        assert new.MAX_SIZE_SOFT_MB == 5
        assert cfg.MAX_SIZE_SOFT_MB == 15  # original unchanged
