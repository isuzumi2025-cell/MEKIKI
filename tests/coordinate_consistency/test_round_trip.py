"""
Round-trip coordinate conversion tests.

Verify that converting PDF -> Web -> PDF preserves coordinates within
the defined tolerance across all combinations of:
  - Page sizes (A4, A3, Letter, Tabloid, B5, custom)
  - Rotations (0, 90, 180, 270)
  - Zoom levels (0.25x .. 4.0x)
  - DPI scales (1.0, 1.5, 2.0, 3.0)

Each test converts known element positions through the full pipeline
and asserts that the recovered PDF coordinates match the originals.
"""

import math
from typing import List

import pytest

from tests.coordinate_consistency.conftest import (
    DEFAULT_TOLERANCE_PT,
    CanonicalPoint,
    KnownElement,
    PageMeta,
    WebPoint,
    pdf_to_web,
    point_distance,
    web_to_pdf,
)


# ---------------------------------------------------------------------------
# Round-trip: PDF -> Web -> PDF
# ---------------------------------------------------------------------------

class TestRoundTripPointConversion:
    """PDF -> Web -> PDF must recover the original within tolerance."""

    def test_single_point_round_trip(
        self,
        page_meta: PageMeta,
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """Center point round-trips within tolerance."""
        original = CanonicalPoint(
            x=page_meta.width / 2, y=page_meta.height / 2, page=1
        )
        web = pdf_to_web(original, page_meta, zoom, dpi_scale)
        recovered = web_to_pdf(web, page_meta, zoom, dpi_scale)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"Round-trip distance {dist:.6f} pt exceeds tolerance "
            f"{DEFAULT_TOLERANCE_PT} pt | rotation={page_meta.rotation} "
            f"zoom={zoom} dpi={dpi_scale}"
        )

    def test_all_known_elements_round_trip(
        self,
        known_elements: List[KnownElement],
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """All known reference elements round-trip within tolerance."""
        for elem in known_elements:
            web = pdf_to_web(elem.pdf_point, elem.page_meta, zoom, dpi_scale)
            recovered = web_to_pdf(web, elem.page_meta, zoom, dpi_scale)
            dist = point_distance(elem.pdf_point, recovered)
            assert dist <= DEFAULT_TOLERANCE_PT, (
                f"Element '{elem.name}' round-trip distance {dist:.6f} pt "
                f"exceeds tolerance {DEFAULT_TOLERANCE_PT} pt | "
                f"original=({elem.pdf_point.x:.2f}, {elem.pdf_point.y:.2f}) "
                f"recovered=({recovered.x:.2f}, {recovered.y:.2f}) "
                f"rotation={elem.page_meta.rotation} zoom={zoom} dpi={dpi_scale}"
            )

    def test_origin_point_round_trip(
        self,
        page_meta: PageMeta,
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """The origin (0, 0) round-trips correctly."""
        original = CanonicalPoint(x=0.0, y=0.0, page=1)
        web = pdf_to_web(original, page_meta, zoom, dpi_scale)
        recovered = web_to_pdf(web, page_meta, zoom, dpi_scale)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"Origin round-trip distance {dist:.6f} pt exceeds tolerance "
            f"{DEFAULT_TOLERANCE_PT} pt"
        )

    def test_max_corner_round_trip(
        self,
        page_meta: PageMeta,
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """Top-right corner (w, h) round-trips correctly."""
        original = CanonicalPoint(
            x=page_meta.width, y=page_meta.height, page=1
        )
        web = pdf_to_web(original, page_meta, zoom, dpi_scale)
        recovered = web_to_pdf(web, page_meta, zoom, dpi_scale)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"Max-corner round-trip distance {dist:.6f} pt exceeds tolerance "
            f"{DEFAULT_TOLERANCE_PT} pt"
        )


# ---------------------------------------------------------------------------
# Round-trip: Web -> PDF -> Web
# ---------------------------------------------------------------------------

class TestReverseRoundTrip:
    """Web -> PDF -> Web must also recover the original."""

    def test_web_to_pdf_to_web(
        self,
        page_meta: PageMeta,
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """A Web-space point survives the reverse round-trip."""
        from tests.coordinate_consistency.conftest import effective_page_size

        eff_w, eff_h = effective_page_size(page_meta)
        scale = zoom * dpi_scale
        # Place the Web point at the center of the rendered page
        original_web = WebPoint(
            x=(eff_w / 2) * scale,
            y=(eff_h / 2) * scale,
            page=1,
        )
        pdf_pt = web_to_pdf(original_web, page_meta, zoom, dpi_scale)
        recovered_web = pdf_to_web(pdf_pt, page_meta, zoom, dpi_scale)

        dx = abs(original_web.x - recovered_web.x)
        dy = abs(original_web.y - recovered_web.y)
        # Tolerance in pixels: scale the PDF-point tolerance
        tol_px = DEFAULT_TOLERANCE_PT * scale
        dist_px = math.sqrt(dx * dx + dy * dy)
        assert dist_px <= tol_px, (
            f"Reverse round-trip pixel distance {dist_px:.6f} exceeds "
            f"tolerance {tol_px:.6f} px"
        )
