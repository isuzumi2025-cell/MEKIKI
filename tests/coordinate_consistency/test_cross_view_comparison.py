"""
Cross-view coordinate comparison tests.

Simulate known element coordinates in both PDF and Web views, convert
both to the canonical PDF-point space, and assert that the difference
does not exceed a predefined tolerance.

This catches real-world bugs such as:
  - Y-axis flip errors (PDF bottom-left vs Web top-left)
  - Rotation miscalculations
  - Scale / DPI misapplication
  - Off-by-one in page dimensions
"""

import math
from typing import List, Tuple

import pytest

from tests.coordinate_consistency.conftest import (
    DEFAULT_TOLERANCE_PT,
    DPI_SCALE,
    CanonicalPoint,
    KnownElement,
    PageMeta,
    WebPoint,
    effective_page_size,
    pdf_to_web,
    point_distance,
    web_to_pdf,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulate_web_coordinate(
    pdf_point: CanonicalPoint,
    meta: PageMeta,
    viewport_scale: float,
    dpi_scale: float,
) -> WebPoint:
    """
    Simulate what the Web renderer would produce for a given PDF-space point.
    This is the 'ground truth' Web coordinate.
    """
    return pdf_to_web(pdf_point, meta, viewport_scale, dpi_scale)


def _compare_in_canonical_space(
    pdf_point: CanonicalPoint,
    web_point: WebPoint,
    meta: PageMeta,
    viewport_scale: float,
    dpi_scale: float,
    tolerance: float = DEFAULT_TOLERANCE_PT,
) -> Tuple[float, bool]:
    """
    Convert the Web point to canonical space and compare with the PDF point.
    Returns (distance, passed).
    """
    converted = web_to_pdf(web_point, meta, viewport_scale, dpi_scale)
    dist = point_distance(pdf_point, converted)
    return dist, dist <= tolerance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrossViewComparison:
    """Compare PDF-sourced and Web-sourced coordinates in canonical space."""

    def test_known_elements_match(
        self,
        known_elements: List[KnownElement],
        zoom: float,
        dpi_scale: float,
    ) -> None:
        """
        For every known element, the Web coordinate (produced by the
        renderer) must convert back to the original PDF coordinate
        within tolerance.
        """
        failures = []
        for elem in known_elements:
            web_pt = _simulate_web_coordinate(
                elem.pdf_point, elem.page_meta, zoom, dpi_scale
            )
            dist, passed = _compare_in_canonical_space(
                elem.pdf_point, web_pt, elem.page_meta, zoom, dpi_scale
            )
            if not passed:
                failures.append(
                    f"  {elem.name}: distance={dist:.6f} pt "
                    f"(tolerance={DEFAULT_TOLERANCE_PT})"
                )
        assert not failures, (
            f"Cross-view mismatch for {len(failures)} element(s) at "
            f"zoom={zoom} dpi={dpi_scale}:\n" + "\n".join(failures)
        )

    def test_y_axis_flip_correctness(
        self,
        page_meta: PageMeta,
        zoom: float,
    ) -> None:
        """
        A point at PDF (x, 0) — bottom edge — should map to the
        bottom of the rendered Web page, and (x, h) to the top.

        This pure Y-flip relationship only holds for rotation=0;
        rotation-specific correctness is validated in
        test_rotation_consistency.py.
        """
        if page_meta.rotation != 0:
            pytest.skip("Y-axis flip test applies to rotation=0 only")

        dpi = 1.0
        w, h = page_meta.width, page_meta.height
        scale = zoom * dpi

        # Bottom edge in PDF -> should be max-Y in Web
        bottom = CanonicalPoint(x=w / 2, y=0.0, page=1)
        web_bottom = pdf_to_web(bottom, page_meta, zoom, dpi)
        assert abs(web_bottom.y - h * scale) <= DEFAULT_TOLERANCE_PT * scale, (
            f"Bottom-edge Y mismatch: web_y={web_bottom.y:.4f} "
            f"expected={h * scale:.4f}"
        )

        # Top edge in PDF -> should be 0 in Web
        top = CanonicalPoint(x=w / 2, y=h, page=1)
        web_top = pdf_to_web(top, page_meta, zoom, dpi)
        assert abs(web_top.y) <= DEFAULT_TOLERANCE_PT * scale, (
            f"Top-edge Y mismatch: web_y={web_top.y:.4f} expected=0"
        )

    def test_x_axis_preserved(
        self,
        page_meta: PageMeta,
        zoom: float,
    ) -> None:
        """
        X coordinates should scale linearly without flip
        (for rotation == 0).
        """
        if page_meta.rotation != 0:
            pytest.skip("X-axis linearity only tested for rotation=0")
        dpi = 1.0
        scale = zoom * dpi
        test_x = page_meta.width * 0.7
        point = CanonicalPoint(x=test_x, y=page_meta.height / 2, page=1)
        web = pdf_to_web(point, page_meta, zoom, dpi)
        expected_x = test_x * scale
        assert abs(web.x - expected_x) <= DEFAULT_TOLERANCE_PT * scale, (
            f"X mismatch: web_x={web.x:.4f} expected={expected_x:.4f}"
        )


class TestCrossViewWithDpiScale:
    """Validate DPI-scale-specific coordinate comparisons."""

    @pytest.mark.parametrize("device_dpi", [1.0, 1.5, 2.0, 3.0])
    def test_dpi_scale_consistency(
        self,
        page_meta: PageMeta,
        zoom: float,
        device_dpi: float,
    ) -> None:
        """
        The same canonical point must compare equal regardless of the
        device DPI used during rendering.
        """
        original = CanonicalPoint(
            x=page_meta.width * 0.3,
            y=page_meta.height * 0.6,
            page=1,
        )
        web = pdf_to_web(original, page_meta, zoom, device_dpi)
        recovered = web_to_pdf(web, page_meta, zoom, device_dpi)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"DPI-scale {device_dpi} round-trip distance {dist:.6f} pt "
            f"exceeds tolerance"
        )


class TestCrossViewEdgeCases:
    """Edge-case scenarios that historically caused coordinate bugs."""

    def test_zero_zoom_raises_or_handles(self, page_meta: PageMeta) -> None:
        """Zero zoom should not produce NaN / Inf coordinates."""
        point = CanonicalPoint(
            x=page_meta.width / 2, y=page_meta.height / 2, page=1
        )
        # With zero zoom the Web coordinates should be zero
        web = pdf_to_web(point, page_meta, viewport_scale=0.0, dpi_scale=1.0)
        assert math.isfinite(web.x) and math.isfinite(web.y), (
            "Zero zoom produced non-finite Web coordinates"
        )

    def test_very_large_zoom(self, page_meta: PageMeta) -> None:
        """Extreme zoom (100x) should still round-trip correctly."""
        original = CanonicalPoint(
            x=page_meta.width / 2, y=page_meta.height / 2, page=1
        )
        web = pdf_to_web(original, page_meta, viewport_scale=100.0, dpi_scale=1.0)
        recovered = web_to_pdf(web, page_meta, viewport_scale=100.0, dpi_scale=1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"100x zoom round-trip distance {dist:.6f} pt exceeds tolerance"
        )

    def test_fractional_coordinates(self, page_meta: PageMeta) -> None:
        """Sub-point fractional coordinates should round-trip accurately."""
        original = CanonicalPoint(x=123.456789, y=654.321012, page=1)
        # Clamp to page bounds
        clamped = CanonicalPoint(
            x=min(original.x, page_meta.width),
            y=min(original.y, page_meta.height),
            page=1,
        )
        web = pdf_to_web(clamped, page_meta, 1.5, 2.0)
        recovered = web_to_pdf(web, page_meta, 1.5, 2.0)
        dist = point_distance(clamped, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT
