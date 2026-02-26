"""
Rotation-specific coordinate consistency tests.

Verify that coordinate conversions are correct for every supported
page rotation (0, 90, 180, 270), and that rotating a page does not
introduce coordinate drift beyond the tolerance.
"""

import math
from typing import List

import pytest

from tests.coordinate_consistency.conftest import (
    DEFAULT_TOLERANCE_PT,
    PAGE_SIZES,
    ROTATIONS,
    CanonicalPoint,
    PageMeta,
    WebPoint,
    apply_rotation,
    effective_page_size,
    pdf_to_web,
    point_distance,
    reverse_rotation,
    web_to_pdf,
)


class TestRotationInverse:
    """apply_rotation and reverse_rotation must be exact inverses."""

    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"rot={r}")
    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_rotation_inverse_property(
        self, rotation: int, page_name: str
    ) -> None:
        """reverse_rotation(apply_rotation(p)) == p for all rotations."""
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=rotation)

        points = [
            (0.0, 0.0),
            (w, h),
            (w / 2, h / 2),
            (w * 0.1, h * 0.9),
            (w * 0.9, h * 0.1),
        ]

        for px, py in points:
            rx, ry = apply_rotation(px, py, meta)
            ux, uy = reverse_rotation(rx, ry, meta)
            dist = math.sqrt((px - ux) ** 2 + (py - uy) ** 2)
            assert dist <= 1e-10, (
                f"Rotation inverse failed: ({px}, {py}) -> ({rx}, {ry}) "
                f"-> ({ux}, {uy}), dist={dist}, rotation={rotation}"
            )


class TestRotationRoundTrip:
    """PDF -> Web -> PDF round-trip for each rotation independently."""

    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"rot={r}")
    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    @pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0], ids=lambda z: f"z={z}")
    def test_round_trip_per_rotation(
        self, rotation: int, page_name: str, zoom: float
    ) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=rotation)
        dpi = 1.0

        # Test 5 strategic points
        test_points = [
            CanonicalPoint(x=w * 0.1, y=h * 0.1, page=1),
            CanonicalPoint(x=w * 0.9, y=h * 0.9, page=1),
            CanonicalPoint(x=w / 2, y=h / 2, page=1),
            CanonicalPoint(x=0.0, y=0.0, page=1),
            CanonicalPoint(x=w, y=h, page=1),
        ]

        for original in test_points:
            web = pdf_to_web(original, meta, zoom, dpi)
            recovered = web_to_pdf(web, meta, zoom, dpi)
            dist = point_distance(original, recovered)
            assert dist <= DEFAULT_TOLERANCE_PT, (
                f"Rotation {rotation} round-trip failed: "
                f"({original.x:.2f}, {original.y:.2f}) -> "
                f"({recovered.x:.2f}, {recovered.y:.2f}), "
                f"dist={dist:.6f}, page={page_name}, zoom={zoom}"
            )


class TestRotationSwapsDimensions:
    """90 and 270 degree rotations must swap effective page dimensions."""

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_90_swaps_dimensions(self, page_name: str) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=90)
        eff_w, eff_h = effective_page_size(meta)
        assert eff_w == h, f"Expected eff_width={h}, got {eff_w}"
        assert eff_h == w, f"Expected eff_height={w}, got {eff_h}"

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_270_swaps_dimensions(self, page_name: str) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=270)
        eff_w, eff_h = effective_page_size(meta)
        assert eff_w == h
        assert eff_h == w

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_0_preserves_dimensions(self, page_name: str) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=0)
        eff_w, eff_h = effective_page_size(meta)
        assert eff_w == w
        assert eff_h == h

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_180_preserves_dimensions(self, page_name: str) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=180)
        eff_w, eff_h = effective_page_size(meta)
        assert eff_w == w
        assert eff_h == h


class TestRotationWebBounds:
    """
    After conversion to Web space, coordinates must remain within the
    rendered page bounds (non-negative, <= effective dimension * scale).
    """

    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"rot={r}")
    @pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0], ids=lambda z: f"z={z}")
    def test_web_coordinates_within_bounds(
        self, rotation: int, zoom: float
    ) -> None:
        w, h = PAGE_SIZES["A4_portrait"]
        meta = PageMeta(width=w, height=h, rotation=rotation)
        dpi = 1.0
        eff_w, eff_h = effective_page_size(meta)
        scale = zoom * dpi

        interior_points = [
            CanonicalPoint(x=w * 0.1, y=h * 0.1, page=1),
            CanonicalPoint(x=w * 0.5, y=h * 0.5, page=1),
            CanonicalPoint(x=w * 0.9, y=h * 0.9, page=1),
        ]

        for pt in interior_points:
            web = pdf_to_web(pt, meta, zoom, dpi)
            # Allow tiny float tolerance for boundary points
            eps = DEFAULT_TOLERANCE_PT * scale
            assert web.x >= -eps, (
                f"Negative web.x={web.x} for rotation={rotation}"
            )
            assert web.y >= -eps, (
                f"Negative web.y={web.y} for rotation={rotation}"
            )
            assert web.x <= eff_w * scale + eps, (
                f"web.x={web.x} exceeds bound {eff_w * scale}"
            )
            assert web.y <= eff_h * scale + eps, (
                f"web.y={web.y} exceeds bound {eff_h * scale}"
            )
