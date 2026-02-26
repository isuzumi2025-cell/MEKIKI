"""
Page-size-specific coordinate consistency tests.

Verify that coordinate conversions work correctly across the full
range of standard and custom page sizes, and that the conversion
logic is not hard-coded to any particular page dimension.
"""

import math
from typing import Tuple

import pytest

from tests.coordinate_consistency.conftest import (
    DEFAULT_TOLERANCE_PT,
    PAGE_SIZES,
    ROTATIONS,
    ZOOM_LEVELS,
    CanonicalPoint,
    PageMeta,
    effective_page_size,
    pdf_to_web,
    point_distance,
    web_to_pdf,
)


class TestPageSizeRoundTrip:
    """Round-trip accuracy must hold for every page size."""

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    @pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0], ids=lambda z: f"z={z}")
    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"r={r}")
    def test_center_point(
        self, page_name: str, zoom: float, rotation: int
    ) -> None:
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=rotation)
        original = CanonicalPoint(x=w / 2, y=h / 2, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"page={page_name} rot={rotation} zoom={zoom}: "
            f"center round-trip dist={dist:.6f}"
        )

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_all_four_corners(self, page_name: str) -> None:
        """All four corners round-trip for each page size (rotation=0, zoom=1)."""
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=0)

        corners = [
            CanonicalPoint(x=0, y=0, page=1),
            CanonicalPoint(x=w, y=0, page=1),
            CanonicalPoint(x=0, y=h, page=1),
            CanonicalPoint(x=w, y=h, page=1),
        ]
        for corner in corners:
            web = pdf_to_web(corner, meta, 1.0, 1.0)
            recovered = web_to_pdf(web, meta, 1.0, 1.0)
            dist = point_distance(corner, recovered)
            assert dist <= DEFAULT_TOLERANCE_PT, (
                f"page={page_name} corner=({corner.x}, {corner.y}) "
                f"dist={dist:.6f}"
            )


class TestPageSizeScaling:
    """Verify that coordinates scale proportionally with page dimensions."""

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_proportional_scaling_x(self, page_name: str) -> None:
        """
        A point at 50% of page width should produce a Web-x at 50%
        of the rendered width (for rotation=0, zoom=1, dpi=1).
        """
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=0)
        point = CanonicalPoint(x=w * 0.5, y=h * 0.5, page=1)
        web = pdf_to_web(point, meta, 1.0, 1.0)
        expected_x = w * 0.5
        assert abs(web.x - expected_x) <= DEFAULT_TOLERANCE_PT, (
            f"page={page_name}: web.x={web.x:.4f} expected={expected_x:.4f}"
        )

    @pytest.mark.parametrize(
        "page_name", list(PAGE_SIZES.keys()), ids=lambda n: f"page={n}"
    )
    def test_proportional_scaling_y(self, page_name: str) -> None:
        """
        A point at 50% of page height (PDF-space) should produce
        a Web-y at 50% of the rendered height (top-left origin).
        """
        w, h = PAGE_SIZES[page_name]
        meta = PageMeta(width=w, height=h, rotation=0)
        point = CanonicalPoint(x=w * 0.5, y=h * 0.5, page=1)
        web = pdf_to_web(point, meta, 1.0, 1.0)
        expected_y = h * 0.5  # h - h/2 = h/2
        assert abs(web.y - expected_y) <= DEFAULT_TOLERANCE_PT, (
            f"page={page_name}: web.y={web.y:.4f} expected={expected_y:.4f}"
        )


class TestCustomPageSizes:
    """Verify with non-standard page sizes to catch hard-coded assumptions."""

    @pytest.mark.parametrize(
        "dims",
        [
            (100.0, 100.0),    # square
            (1.0, 1.0),        # tiny
            (5000.0, 5000.0),  # huge
            (10.0, 1000.0),    # extreme portrait
            (1000.0, 10.0),    # extreme landscape
            (595.28, 841.89),  # A4 (standard check)
        ],
        ids=["square", "tiny", "huge", "tall", "wide", "A4"],
    )
    @pytest.mark.parametrize("rotation", ROTATIONS, ids=lambda r: f"r={r}")
    @pytest.mark.parametrize("zoom", [0.5, 1.0, 3.0], ids=lambda z: f"z={z}")
    def test_arbitrary_page_size_round_trip(
        self,
        dims: Tuple[float, float],
        rotation: int,
        zoom: float,
    ) -> None:
        w, h = dims
        meta = PageMeta(width=w, height=h, rotation=rotation)
        # Place point at 30% / 70% to avoid boundaries
        original = CanonicalPoint(x=w * 0.3, y=h * 0.7, page=1)
        web = pdf_to_web(original, meta, zoom, 1.0)
        recovered = web_to_pdf(web, meta, zoom, 1.0)
        dist = point_distance(original, recovered)
        assert dist <= DEFAULT_TOLERANCE_PT, (
            f"dims=({w}, {h}) rot={rotation} zoom={zoom}: "
            f"dist={dist:.6f}"
        )


class TestMultiPageConsistency:
    """Pages with different sizes in the same document."""

    def test_different_page_sizes_independent(self) -> None:
        """
        Coordinates on page 1 (A4) and page 2 (Letter) should each
        round-trip independently.
        """
        pages = [
            (PageMeta(width=595.28, height=841.89, rotation=0), 1),
            (PageMeta(width=612.0, height=792.0, rotation=0), 2),
        ]
        for meta, page_num in pages:
            original = CanonicalPoint(
                x=meta.width / 2, y=meta.height / 2, page=page_num
            )
            web = pdf_to_web(original, meta, 1.0, 1.0)
            recovered = web_to_pdf(web, meta, 1.0, 1.0)
            dist = point_distance(original, recovered)
            assert dist <= DEFAULT_TOLERANCE_PT, (
                f"Page {page_num} round-trip dist={dist:.6f}"
            )
            assert recovered.page == page_num

    def test_mixed_rotation_pages(self) -> None:
        """Pages with different rotations should each convert correctly."""
        pages = [
            PageMeta(width=595.28, height=841.89, rotation=0),
            PageMeta(width=595.28, height=841.89, rotation=90),
            PageMeta(width=595.28, height=841.89, rotation=180),
            PageMeta(width=595.28, height=841.89, rotation=270),
        ]
        for i, meta in enumerate(pages, start=1):
            original = CanonicalPoint(
                x=meta.width * 0.4, y=meta.height * 0.6, page=i
            )
            web = pdf_to_web(original, meta, 1.5, 2.0)
            recovered = web_to_pdf(web, meta, 1.5, 2.0)
            dist = point_distance(original, recovered)
            assert dist <= DEFAULT_TOLERANCE_PT, (
                f"Page {i} (rot={meta.rotation}) dist={dist:.6f}"
            )
