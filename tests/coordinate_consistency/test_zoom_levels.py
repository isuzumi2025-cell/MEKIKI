"""
Zoom-level-specific coordinate consistency tests.

Verify that coordinate conversions remain accurate across a wide
range of zoom / viewport scale factors, including edge cases like
very small and very large zoom values.
"""

import math
from typing import List

import pytest

from tests.coordinate_consistency.conftest import (
    DEFAULT_TOLERANCE_PT,
    PAGE_SIZES,
    ROTATIONS,
    ZOOM_LEVELS,
    CanonicalPoint,
    PageMeta,
    WebPoint,
    effective_page_size,
    pdf_to_web,
    point_distance,
    web_to_pdf,
)


class TestZoomLevelRoundTrip:
    """Round-trip accuracy must hold for every zoom level."""

    @pytest.mark.parametrize("zoom", ZOOM_LEVELS, ids=lambda z: f"z={z}")
    def test_a4_center_all_zooms(self, zoom: float) -> None:
        meta = PageMeta(width=595.28, height=841.89, rotation=0)
        original = CanonicalPoint(x=297.64, y=420.945, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"zoom={zoom}: dist={dist:.6f}"
        )

    @pytest.mark.parametrize("zoom", ZOOM_LEVELS, ids=lambda z: f"z={z}")
    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"r={r}")
    def test_all_zooms_all_rotations(
        self, zoom: float, rotation: int
    ) -> None:
        meta = PageMeta(width=612.0, height=792.0, rotation=rotation)
        original = CanonicalPoint(x=306.0, y=396.0, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"zoom={zoom} rot={rotation}: dist={dist:.6f}"
        )


class TestZoomScaleLinearity:
    """Web coordinates should scale linearly with zoom."""

    def test_double_zoom_doubles_web_coordinates(self) -> None:
        """At 2x zoom, Web coordinates should be exactly 2x those at 1x."""
        meta = PageMeta(width=595.28, height=841.89, rotation=0)
        point = CanonicalPoint(x=100.0, y=200.0, page=1)

        web_1x = pdf_to_web(point, meta, 1.0, 1.0)
        web_2x = pdf_to_web(point, meta, 2.0, 1.0)

        assert abs(web_2x.x - 2.0 * web_1x.x) <= 1e-10, (
            f"X not doubled: 1x={web_1x.x} 2x={web_2x.x}"
        )
        assert abs(web_2x.y - 2.0 * web_1x.y) <= 1e-10, (
            f"Y not doubled: 1x={web_1x.y} 2x={web_2x.y}"
        )

    @pytest.mark.parametrize("zoom", ZOOM_LEVELS, ids=lambda z: f"z={z}")
    def test_zoom_ratio_preserved(self, zoom: float) -> None:
        """Web coords at zoom z should be z times those at zoom 1."""
        meta = PageMeta(width=612.0, height=792.0, rotation=0)
        point = CanonicalPoint(x=150.0, y=300.0, page=1)

        web_1 = pdf_to_web(point, meta, 1.0, 1.0)
        web_z = pdf_to_web(point, meta, zoom, 1.0)

        if zoom == 0:
            # Special case: zero zoom gives zero coords
            assert web_z.x == 0.0
            assert web_z.y == 0.0
        else:
            assert abs(web_z.x - zoom * web_1.x) <= 1e-8, (
                f"X ratio broken at zoom={zoom}"
            )
            assert abs(web_z.y - zoom * web_1.y) <= 1e-8, (
                f"Y ratio broken at zoom={zoom}"
            )


class TestExtremeZoomLevels:
    """Edge cases with very small or very large zoom values."""

    @pytest.mark.parametrize(
        "zoom", [0.01, 0.1, 10.0, 50.0, 100.0],
        ids=lambda z: f"z={z}",
    )
    def test_extreme_zoom_round_trip(self, zoom: float) -> None:
        meta = PageMeta(width=595.28, height=841.89, rotation=0)
        original = CanonicalPoint(x=200.0, y=400.0, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"Extreme zoom {zoom}: dist={dist:.6f}"
        )

    def test_zero_zoom_produces_zero_web(self) -> None:
        meta = PageMeta(width=595.28, height=841.89, rotation=0)
        point = CanonicalPoint(x=100.0, y=200.0, page=1)
        web = pdf_to_web(point, meta, 0.0, 1.0)
        assert web.x == 0.0
        assert web.y == 0.0

    @pytest.mark.parametrize(
        "zoom", [0.01, 0.1, 10.0, 50.0, 100.0],
        ids=lambda z: f"z={z}",
    )
    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"r={r}")
    def test_extreme_zoom_with_rotation(
        self, zoom: float, rotation: int
    ) -> None:
        meta = PageMeta(width=612.0, height=792.0, rotation=rotation)
        original = CanonicalPoint(x=306.0, y=396.0, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"zoom={zoom} rot={rotation}: dist={dist:.6f}"
        )


class TestZoomDpiInteraction:
    """Zoom and DPI scale should compose multiplicatively."""

    @pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0], ids=lambda z: f"z={z}")
    @pytest.mark.parametrize("dpi", [1.0, 2.0, 3.0], ids=lambda d: f"d={d}")
    def test_zoom_dpi_product(self, zoom: float, dpi: float) -> None:
        """
        pdf_to_web(zoom=z, dpi=d) should equal pdf_to_web(zoom=z*d, dpi=1).
        """
        meta = PageMeta(width=595.28, height=841.89, rotation=0)
        point = CanonicalPoint(x=200.0, y=400.0, page=1)

        web_separate = pdf_to_web(point, meta, zoom, dpi)
        web_combined = pdf_to_web(point, meta, zoom * dpi, 1.0)

        assert abs(web_separate.x - web_combined.x) <= 1e-8, (
            f"X mismatch: separate={web_separate.x} combined={web_combined.x}"
        )
        assert abs(web_separate.y - web_combined.y) <= 1e-8, (
            f"Y mismatch: separate={web_separate.y} combined={web_combined.y}"
        )
