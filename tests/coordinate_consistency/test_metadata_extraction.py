"""
Tests for the PDF page metadata extraction tool.

Uses synthetic PDF files created in-memory (when PyMuPDF is available)
or validates the extraction logic with mock data.
"""

import json
import math
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from tools.extract_page_metadata import extract_metadata, save_metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_synthetic_pdf(
    pages: list,
    output_path: str,
) -> None:
    """
    Create a minimal PDF with the given page specifications.
    Each entry in *pages* is (width_pt, height_pt, rotation_deg).
    Requires PyMuPDF.
    """
    import fitz

    doc = fitz.open()
    for w, h, rot in pages:
        page = doc.new_page(width=w, height=h)
        page.set_rotation(rot)
    doc.save(output_path)
    doc.close()


def _has_pymupdf() -> bool:
    try:
        import fitz
        return True
    except ImportError:
        return False


needs_pymupdf = pytest.mark.skipif(
    not _has_pymupdf(), reason="PyMuPDF not installed"
)


# ---------------------------------------------------------------------------
# Tests with real PDFs (require PyMuPDF)
# ---------------------------------------------------------------------------

@needs_pymupdf
class TestExtractMetadataReal:
    """Tests using real in-memory PDFs via PyMuPDF."""

    def test_single_a4_page(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "a4.pdf")
        _create_synthetic_pdf([(595.28, 841.89, 0)], pdf_path)
        meta = extract_metadata(pdf_path)
        assert 1 in meta
        assert abs(meta[1]["width"] - 595.28) < 0.1
        assert abs(meta[1]["height"] - 841.89) < 0.1
        assert meta[1]["rotation"] == 0

    def test_rotated_page(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "rotated.pdf")
        _create_synthetic_pdf([(595.28, 841.89, 90)], pdf_path)
        meta = extract_metadata(pdf_path)
        assert meta[1]["rotation"] == 90

    def test_multiple_pages(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "multi.pdf")
        pages = [
            (595.28, 841.89, 0),    # A4 portrait
            (841.89, 595.28, 0),    # A4 landscape
            (612.0, 792.0, 180),    # US Letter rotated 180
        ]
        _create_synthetic_pdf(pages, pdf_path)
        meta = extract_metadata(pdf_path)
        assert len(meta) == 3
        assert meta[2]["rotation"] == 0    # landscape is just wider
        assert meta[3]["rotation"] == 180

    def test_all_rotations(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "all_rot.pdf")
        pages = [
            (595.28, 841.89, 0),
            (595.28, 841.89, 90),
            (595.28, 841.89, 180),
            (595.28, 841.89, 270),
        ]
        _create_synthetic_pdf(pages, pdf_path)
        meta = extract_metadata(pdf_path)
        assert meta[1]["rotation"] == 0
        assert meta[2]["rotation"] == 90
        assert meta[3]["rotation"] == 180
        assert meta[4]["rotation"] == 270

    def test_save_and_reload(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "save_test.pdf")
        json_path = str(tmp_path / "metadata.json")
        _create_synthetic_pdf([(612.0, 792.0, 0)], pdf_path)
        save_metadata(pdf_path, json_path)

        with open(json_path) as f:
            loaded = json.load(f)
        assert "1" in loaded
        assert abs(loaded["1"]["width"] - 612.0) < 0.1

    def test_custom_page_size(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "custom.pdf")
        _create_synthetic_pdf([(300.0, 400.0, 0)], pdf_path)
        meta = extract_metadata(pdf_path)
        assert abs(meta[1]["width"] - 300.0) < 0.1
        assert abs(meta[1]["height"] - 400.0) < 0.1


# ---------------------------------------------------------------------------
# Tests that don't require PyMuPDF
# ---------------------------------------------------------------------------

class TestExtractMetadataErrors:
    """Error handling in metadata extraction."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            extract_metadata("/nonexistent/path/test.pdf")

    @patch("tools.extract_page_metadata.fitz", None)
    def test_missing_pymupdf_raises(self) -> None:
        with pytest.raises(ImportError):
            extract_metadata("/any/path.pdf")
