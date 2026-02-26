"""
Extract page geometry metadata (width, height, rotation) from PDF files.

Uses PyMuPDF (fitz) to read each page's dimensions and rotation,
outputting a JSON file that the web client can consume for accurate
coordinate conversion.

Usage:
    python tools/extract_page_metadata.py <pdf_path> <output_json_path>
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]


def extract_metadata(pdf_path: str) -> Dict[int, Dict[str, Any]]:
    """
    Extract page metadata from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary mapping 1-based page numbers to metadata dicts
        containing width (PDF points), height (PDF points), and rotation (degrees).

    Raises:
        ImportError: If PyMuPDF is not installed.
        FileNotFoundError: If the PDF file does not exist.
    """
    if fitz is None:
        raise ImportError(
            "PyMuPDF (fitz) is required. Install with: pip install PyMuPDF"
        )

    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    metadata: Dict[int, Dict[str, Any]] = {}
    with fitz.open(str(pdf)) as doc:
        for page_index in range(len(doc)):
            page = doc[page_index]
            rect = page.rect
            metadata[page_index + 1] = {
                "width": rect.width,
                "height": rect.height,
                "rotation": page.rotation,
            }
    return metadata


def save_metadata(pdf_path: str, output_path: str) -> None:
    """
    Extract and save page metadata to a JSON file.

    Args:
        pdf_path: Path to the PDF file.
        output_path: Path for the output JSON file.
    """
    metadata = extract_metadata(pdf_path)
    # JSON keys must be strings
    serializable = {str(k): v for k, v in metadata.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <pdf_path> <output_json_path>")
        sys.exit(1)
    save_metadata(sys.argv[1], sys.argv[2])
    print(f"Metadata written to {sys.argv[2]}")
