"""
Comprehensive tests for PDF <-> normalised coordinate conversion.

Covers:
- point_pdf_to_norm
- rect_pdf_to_norm
- rect_norm_to_pdf
- PageGeometry construction & validation
- Edge cases (origin, boundary, full-page)
- Invalid inputs (negative, out-of-range, inverted)
- Various page sizes (Letter, A4, A3, custom)
- DPI scaling (72, 150, 300)
- Rotations (0, 90, 180, 270)
- Round-trip consistency (PDF -> norm -> PDF)
"""

from __future__ import annotations

import math

import pytest

from mekiki.pdf_geometry import PageGeometry
from mekiki.annotations.geometry import (
    point_pdf_to_norm,
    rect_pdf_to_norm,
    rect_norm_to_pdf,
)


# ====================================================================
# Fixtures – common page geometries
# ====================================================================

# Standard page sizes in PDF points (1 pt = 1/72 in)
LETTER_W, LETTER_H = 612.0, 792.0  # 8.5 x 11 in
A4_W, A4_H = 595.276, 841.89       # 210 x 297 mm
A3_W, A3_H = 841.89, 1190.55       # 297 x 420 mm
SQUARE_W, SQUARE_H = 500.0, 500.0


@pytest.fixture
def letter_page() -> PageGeometry:
    return PageGeometry(page_number=1, width_pt=LETTER_W, height_pt=LETTER_H)


@pytest.fixture
def a4_page() -> PageGeometry:
    return PageGeometry(page_number=1, width_pt=A4_W, height_pt=A4_H)


@pytest.fixture
def a3_page() -> PageGeometry:
    return PageGeometry(page_number=1, width_pt=A3_W, height_pt=A3_H)


@pytest.fixture
def square_page() -> PageGeometry:
    return PageGeometry(page_number=1, width_pt=SQUARE_W, height_pt=SQUARE_H)


@pytest.fixture(params=[0, 90, 180, 270], ids=lambda r: f"rot{r}")
def letter_rotated(request: pytest.FixtureRequest) -> PageGeometry:
    return PageGeometry(
        page_number=1,
        width_pt=LETTER_W,
        height_pt=LETTER_H,
        rotation=request.param,
    )


# ====================================================================
# 1. PageGeometry construction & validation
# ====================================================================


class TestPageGeometryConstruction:
    """Validate PageGeometry creation, defaults and error paths."""

    def test_basic_construction(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612.0, height_pt=792.0)
        assert pg.page_number == 1
        assert pg.width_pt == 612.0
        assert pg.height_pt == 792.0
        assert pg.rotation == 0

    def test_rotation_default(self) -> None:
        pg = PageGeometry(page_number=2, width_pt=100, height_pt=200)
        assert pg.rotation == 0

    @pytest.mark.parametrize("rot", [0, 90, 180, 270])
    def test_valid_rotations(self, rot: int) -> None:
        pg = PageGeometry(page_number=1, width_pt=100, height_pt=200, rotation=rot)
        assert pg.rotation == rot

    @pytest.mark.parametrize("rot", [45, 60, 120, 360, -90, 1])
    def test_invalid_rotation_raises(self, rot: int) -> None:
        with pytest.raises(ValueError, match="rotation"):
            PageGeometry(page_number=1, width_pt=100, height_pt=200, rotation=rot)

    def test_zero_width_raises(self) -> None:
        with pytest.raises(ValueError, match="width_pt"):
            PageGeometry(page_number=1, width_pt=0, height_pt=200)

    def test_negative_width_raises(self) -> None:
        with pytest.raises(ValueError, match="width_pt"):
            PageGeometry(page_number=1, width_pt=-10, height_pt=200)

    def test_zero_height_raises(self) -> None:
        with pytest.raises(ValueError, match="height_pt"):
            PageGeometry(page_number=1, width_pt=200, height_pt=0)

    def test_negative_height_raises(self) -> None:
        with pytest.raises(ValueError, match="height_pt"):
            PageGeometry(page_number=1, width_pt=200, height_pt=-5)

    def test_frozen(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=100, height_pt=200)
        with pytest.raises(AttributeError):
            pg.width_pt = 300  # type: ignore[misc]


class TestPageGeometryEffectiveDimensions:
    """Effective dimensions must swap for 90/270 rotations."""

    def test_no_rotation(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=0)
        assert pg.effective_width_pt == 612
        assert pg.effective_height_pt == 792

    def test_rotation_90(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        assert pg.effective_width_pt == 792
        assert pg.effective_height_pt == 612

    def test_rotation_180(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=180)
        assert pg.effective_width_pt == 612
        assert pg.effective_height_pt == 792

    def test_rotation_270(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=270)
        assert pg.effective_width_pt == 792
        assert pg.effective_height_pt == 612


class TestPageGeometryPixelHelpers:
    """width_px / height_px at various DPI values."""

    def test_default_dpi_72(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792)
        assert pg.width_px() == pytest.approx(612.0)
        assert pg.height_px() == pytest.approx(792.0)

    def test_dpi_150(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792)
        assert pg.width_px(dpi=150) == pytest.approx(612 * 150 / 72)
        assert pg.height_px(dpi=150) == pytest.approx(792 * 150 / 72)

    def test_dpi_300(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792)
        assert pg.width_px(dpi=300) == pytest.approx(612 * 300 / 72)
        assert pg.height_px(dpi=300) == pytest.approx(792 * 300 / 72)

    def test_pixel_with_rotation_90_dpi_300(self) -> None:
        pg = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        # effective: w=792, h=612
        assert pg.width_px(dpi=300) == pytest.approx(792 * 300 / 72)
        assert pg.height_px(dpi=300) == pytest.approx(612 * 300 / 72)


# ====================================================================
# 2. point_pdf_to_norm
# ====================================================================


class TestPointPdfToNorm:
    """Unit tests for single-point PDF -> normalised conversion."""

    # ------ basic / happy path ------

    def test_origin_bottom_left(self, letter_page: PageGeometry) -> None:
        """PDF origin (0, 0) bottom-left -> norm (0, 1) top-left frame."""
        x, y = point_pdf_to_norm(0, 0, letter_page)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(1.0)

    def test_top_right(self, letter_page: PageGeometry) -> None:
        """PDF top-right -> norm (1, 0)."""
        x, y = point_pdf_to_norm(LETTER_W, LETTER_H, letter_page)
        assert x == pytest.approx(1.0)
        assert y == pytest.approx(0.0)

    def test_center(self, letter_page: PageGeometry) -> None:
        cx, cy = LETTER_W / 2, LETTER_H / 2
        x, y = point_pdf_to_norm(cx, cy, letter_page)
        assert x == pytest.approx(0.5)
        assert y == pytest.approx(0.5)

    def test_bottom_right(self, letter_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(LETTER_W, 0, letter_page)
        assert x == pytest.approx(1.0)
        assert y == pytest.approx(1.0)

    def test_top_left(self, letter_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(0, LETTER_H, letter_page)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(0.0)

    # ------ A4 page ------

    def test_a4_center(self, a4_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(A4_W / 2, A4_H / 2, a4_page)
        assert x == pytest.approx(0.5, abs=1e-6)
        assert y == pytest.approx(0.5, abs=1e-6)

    def test_a4_quarter_point(self, a4_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(A4_W / 4, A4_H * 3 / 4, a4_page)
        assert x == pytest.approx(0.25, abs=1e-6)
        assert y == pytest.approx(0.25, abs=1e-6)

    # ------ A3 page ------

    def test_a3_origin(self, a3_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(0, 0, a3_page)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(1.0)

    # ------ Square page ------

    def test_square_center(self, square_page: PageGeometry) -> None:
        x, y = point_pdf_to_norm(250, 250, square_page)
        assert x == pytest.approx(0.5)
        assert y == pytest.approx(0.5)

    # ------ Arbitrary fractional point ------

    def test_arbitrary_point_letter(self, letter_page: PageGeometry) -> None:
        # 1/3 from left, 1/4 from bottom in PDF
        x_pt = LETTER_W / 3
        y_pt = LETTER_H / 4
        x, y = point_pdf_to_norm(x_pt, y_pt, letter_page)
        assert x == pytest.approx(1 / 3, abs=1e-9)
        assert y == pytest.approx(0.75, abs=1e-9)

    # ------ Invalid inputs ------

    def test_negative_x_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x_pt"):
            point_pdf_to_norm(-1, 100, letter_page)

    def test_negative_y_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y_pt"):
            point_pdf_to_norm(100, -1, letter_page)

    def test_x_exceeds_width(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x_pt"):
            point_pdf_to_norm(LETTER_W + 1, 100, letter_page)

    def test_y_exceeds_height(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y_pt"):
            point_pdf_to_norm(100, LETTER_H + 1, letter_page)


class TestPointPdfToNormRotated:
    """point_pdf_to_norm with rotated pages."""

    def test_rotation_90_center(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        # effective: w=792, h=612
        x, y = point_pdf_to_norm(396, 306, page)
        assert x == pytest.approx(0.5, abs=1e-6)
        assert y == pytest.approx(0.5, abs=1e-6)

    def test_rotation_180_center(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=180)
        x, y = point_pdf_to_norm(306, 396, page)
        assert x == pytest.approx(0.5, abs=1e-6)
        assert y == pytest.approx(0.5, abs=1e-6)

    def test_rotation_270_center(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=270)
        # effective: w=792, h=612
        x, y = point_pdf_to_norm(396, 306, page)
        assert x == pytest.approx(0.5, abs=1e-6)
        assert y == pytest.approx(0.5, abs=1e-6)

    def test_rotation_90_origin(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        # effective: w=792, h=612
        x, y = point_pdf_to_norm(0, 0, page)
        assert x == pytest.approx(0.0)
        assert y == pytest.approx(1.0)

    def test_rotation_90_bounds_reject_original_dims(self) -> None:
        """After 90-deg rotation, the original width (612) exceeds effective height (612).
        But a point at (0, 700) should fail because effective height is 612."""
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        with pytest.raises(ValueError, match="y_pt"):
            point_pdf_to_norm(0, 700, page)

    def test_rotation_90_max_x(self) -> None:
        """Max x is now effective_width = 792."""
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        x, y = point_pdf_to_norm(792, 0, page)
        assert x == pytest.approx(1.0)

    def test_all_rotations_center_is_half(self, letter_rotated: PageGeometry) -> None:
        """Center point should always normalise to (0.5, 0.5)."""
        cx = letter_rotated.effective_width_pt / 2
        cy = letter_rotated.effective_height_pt / 2
        x, y = point_pdf_to_norm(cx, cy, letter_rotated)
        assert x == pytest.approx(0.5, abs=1e-9)
        assert y == pytest.approx(0.5, abs=1e-9)


# ====================================================================
# 3. rect_pdf_to_norm
# ====================================================================


class TestRectPdfToNorm:
    """Unit tests for rectangle PDF -> normalised conversion."""

    def test_full_page(self, letter_page: PageGeometry) -> None:
        """Full-page rect should normalise to (0, 0, 1, 1)."""
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, LETTER_W, LETTER_H, letter_page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_bottom_left_quarter(self, letter_page: PageGeometry) -> None:
        """Bottom-left quarter of the page."""
        xn, yn, wn, hn = rect_pdf_to_norm(
            0, 0, LETTER_W / 2, LETTER_H / 2, letter_page
        )
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.5)   # flipped
        assert wn == pytest.approx(0.5)
        assert hn == pytest.approx(0.5)

    def test_top_right_quarter(self, letter_page: PageGeometry) -> None:
        """Top-right quarter of the page."""
        xn, yn, wn, hn = rect_pdf_to_norm(
            LETTER_W / 2, LETTER_H / 2, LETTER_W, LETTER_H, letter_page
        )
        assert xn == pytest.approx(0.5)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(0.5)
        assert hn == pytest.approx(0.5)

    def test_center_small_rect(self, letter_page: PageGeometry) -> None:
        """Small rect centred on the page."""
        margin_x = LETTER_W * 0.25
        margin_y = LETTER_H * 0.25
        xn, yn, wn, hn = rect_pdf_to_norm(
            margin_x, margin_y, LETTER_W - margin_x, LETTER_H - margin_y, letter_page
        )
        assert xn == pytest.approx(0.25)
        assert yn == pytest.approx(0.25)
        assert wn == pytest.approx(0.5)
        assert hn == pytest.approx(0.5)

    def test_a4_full_page(self, a4_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, A4_W, A4_H, a4_page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_a3_full_page(self, a3_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, A3_W, A3_H, a3_page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_square_center_rect(self, square_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(125, 125, 375, 375, square_page)
        assert xn == pytest.approx(0.25)
        assert yn == pytest.approx(0.25)
        assert wn == pytest.approx(0.5)
        assert hn == pytest.approx(0.5)

    def test_thin_horizontal_strip(self, letter_page: PageGeometry) -> None:
        """Thin strip across top of page (PDF coords: y near LETTER_H)."""
        strip_h = 10.0  # 10pt tall
        xn, yn, wn, hn = rect_pdf_to_norm(
            0, LETTER_H - strip_h, LETTER_W, LETTER_H, letter_page
        )
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(strip_h / LETTER_H, abs=1e-9)

    def test_thin_vertical_strip(self, letter_page: PageGeometry) -> None:
        """Thin strip along left side."""
        strip_w = 10.0
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, strip_w, LETTER_H, letter_page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(strip_w / LETTER_W, abs=1e-9)
        assert hn == pytest.approx(1.0)

    def test_single_point_rect(self, letter_page: PageGeometry) -> None:
        """Degenerate rect with zero area."""
        xn, yn, wn, hn = rect_pdf_to_norm(100, 200, 100, 200, letter_page)
        assert wn == pytest.approx(0.0)
        assert hn == pytest.approx(0.0)

    # ------ Invalid inputs ------

    def test_inverted_x_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="Inverted x"):
            rect_pdf_to_norm(300, 0, 100, 792, letter_page)

    def test_inverted_y_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="Inverted y"):
            rect_pdf_to_norm(0, 500, 612, 100, letter_page)

    def test_negative_x0_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x-range"):
            rect_pdf_to_norm(-10, 0, 612, 792, letter_page)

    def test_x1_exceeds_width(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x-range"):
            rect_pdf_to_norm(0, 0, LETTER_W + 1, LETTER_H, letter_page)

    def test_negative_y0_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y-range"):
            rect_pdf_to_norm(0, -5, 612, 792, letter_page)

    def test_y1_exceeds_height(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y-range"):
            rect_pdf_to_norm(0, 0, LETTER_W, LETTER_H + 1, letter_page)


class TestRectPdfToNormRotated:
    """rect_pdf_to_norm with rotated pages."""

    def test_full_page_rot90(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        # effective: w=792, h=612
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, 792, 612, page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_full_page_rot270(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=270)
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, 792, 612, page)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_half_page_rot90(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        # effective: w=792, h=612  -> left half in norm
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, 396, 612, page)
        assert xn == pytest.approx(0.0)
        assert yn == pytest.approx(0.0)
        assert wn == pytest.approx(0.5)
        assert hn == pytest.approx(1.0)

    def test_center_all_rotations(self, letter_rotated: PageGeometry) -> None:
        """A centered rect should stay centered in normalised space."""
        ew = letter_rotated.effective_width_pt
        eh = letter_rotated.effective_height_pt
        xn, yn, wn, hn = rect_pdf_to_norm(
            ew * 0.25, eh * 0.25, ew * 0.75, eh * 0.75, letter_rotated
        )
        assert xn == pytest.approx(0.25, abs=1e-9)
        assert yn == pytest.approx(0.25, abs=1e-9)
        assert wn == pytest.approx(0.5, abs=1e-9)
        assert hn == pytest.approx(0.5, abs=1e-9)


# ====================================================================
# 4. rect_norm_to_pdf
# ====================================================================


class TestRectNormToPdf:
    """Unit tests for rectangle normalised -> PDF conversion."""

    def test_full_page(self, letter_page: PageGeometry) -> None:
        x0, y0, x1, y1 = rect_norm_to_pdf(0, 0, 1, 1, letter_page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(LETTER_W)
        assert y1 == pytest.approx(LETTER_H)

    def test_top_left_quarter(self, letter_page: PageGeometry) -> None:
        """Norm (0, 0, 0.5, 0.5) => top-left quarter in visual space.
        In PDF coords: upper half (y from H/2 to H), left half (x 0 to W/2)."""
        x0, y0, x1, y1 = rect_norm_to_pdf(0, 0, 0.5, 0.5, letter_page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(LETTER_H / 2)
        assert x1 == pytest.approx(LETTER_W / 2)
        assert y1 == pytest.approx(LETTER_H)

    def test_bottom_right_quarter(self, letter_page: PageGeometry) -> None:
        """Norm (0.5, 0.5, 0.5, 0.5) => bottom-right in visual space."""
        x0, y0, x1, y1 = rect_norm_to_pdf(0.5, 0.5, 0.5, 0.5, letter_page)
        assert x0 == pytest.approx(LETTER_W / 2)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(LETTER_W)
        assert y1 == pytest.approx(LETTER_H / 2)

    def test_a4_full_page(self, a4_page: PageGeometry) -> None:
        x0, y0, x1, y1 = rect_norm_to_pdf(0, 0, 1, 1, a4_page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(A4_W)
        assert y1 == pytest.approx(A4_H)

    def test_a3_full_page(self, a3_page: PageGeometry) -> None:
        x0, y0, x1, y1 = rect_norm_to_pdf(0, 0, 1, 1, a3_page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(A3_W)
        assert y1 == pytest.approx(A3_H)

    def test_zero_size_rect(self, letter_page: PageGeometry) -> None:
        """Point-like rect."""
        x0, y0, x1, y1 = rect_norm_to_pdf(0.5, 0.5, 0.0, 0.0, letter_page)
        assert x0 == pytest.approx(x1)
        assert y0 == pytest.approx(y1)

    # ------ Invalid normalised inputs ------

    def test_negative_x_norm_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x_norm"):
            rect_norm_to_pdf(-0.1, 0, 0.5, 0.5, letter_page)

    def test_negative_y_norm_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y_norm"):
            rect_norm_to_pdf(0, -0.1, 0.5, 0.5, letter_page)

    def test_negative_w_norm_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="w_norm"):
            rect_norm_to_pdf(0, 0, -0.1, 0.5, letter_page)

    def test_negative_h_norm_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="h_norm"):
            rect_norm_to_pdf(0, 0, 0.5, -0.1, letter_page)

    def test_x_norm_exceeds_1_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x_norm"):
            rect_norm_to_pdf(1.1, 0, 0.5, 0.5, letter_page)

    def test_w_norm_exceeds_1_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="w_norm"):
            rect_norm_to_pdf(0, 0, 1.1, 0.5, letter_page)

    def test_x_plus_w_exceeds_1_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="x_norm \\+ w_norm"):
            rect_norm_to_pdf(0.6, 0, 0.5, 0.5, letter_page)

    def test_y_plus_h_exceeds_1_raises(self, letter_page: PageGeometry) -> None:
        with pytest.raises(ValueError, match="y_norm \\+ h_norm"):
            rect_norm_to_pdf(0, 0.6, 0.5, 0.5, letter_page)


class TestRectNormToPdfRotated:
    """rect_norm_to_pdf with rotated pages."""

    def test_full_page_rot90(self) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=90)
        x0, y0, x1, y1 = rect_norm_to_pdf(0, 0, 1, 1, page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(792.0)  # effective width
        assert y1 == pytest.approx(612.0)  # effective height

    def test_center_all_rotations(self, letter_rotated: PageGeometry) -> None:
        """Norm (0.25, 0.25, 0.5, 0.5) always maps to the center 50%."""
        x0, y0, x1, y1 = rect_norm_to_pdf(0.25, 0.25, 0.5, 0.5, letter_rotated)
        ew = letter_rotated.effective_width_pt
        eh = letter_rotated.effective_height_pt
        assert x0 == pytest.approx(ew * 0.25, abs=1e-6)
        assert y0 == pytest.approx(eh * 0.25, abs=1e-6)
        assert x1 == pytest.approx(ew * 0.75, abs=1e-6)
        assert y1 == pytest.approx(eh * 0.75, abs=1e-6)


# ====================================================================
# 5. Round-trip / integration tests
# ====================================================================


class TestRoundTrip:
    """rect_pdf_to_norm -> rect_norm_to_pdf should be identity (and vice-versa)."""

    @pytest.mark.parametrize(
        "x0,y0,x1,y1",
        [
            (0, 0, LETTER_W, LETTER_H),
            (0, 0, LETTER_W / 2, LETTER_H / 2),
            (LETTER_W / 4, LETTER_H / 4, LETTER_W * 3 / 4, LETTER_H * 3 / 4),
            (100, 200, 400, 600),
            (0, 0, 1, 1),  # tiny rect
        ],
        ids=["full", "half", "center50", "arbitrary", "tiny"],
    )
    def test_pdf_norm_pdf_letter(
        self, letter_page: PageGeometry, x0: float, y0: float, x1: float, y1: float
    ) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(x0, y0, x1, y1, letter_page)
        rx0, ry0, rx1, ry1 = rect_norm_to_pdf(xn, yn, wn, hn, letter_page)
        assert rx0 == pytest.approx(x0, abs=1e-9)
        assert ry0 == pytest.approx(y0, abs=1e-9)
        assert rx1 == pytest.approx(x1, abs=1e-9)
        assert ry1 == pytest.approx(y1, abs=1e-9)

    @pytest.mark.parametrize(
        "xn,yn,wn,hn",
        [
            (0.0, 0.0, 1.0, 1.0),
            (0.0, 0.0, 0.5, 0.5),
            (0.25, 0.25, 0.5, 0.5),
            (0.1, 0.2, 0.3, 0.4),
            (0.0, 0.0, 0.01, 0.01),  # tiny
        ],
        ids=["full", "half_tl", "center50", "arbitrary", "tiny"],
    )
    def test_norm_pdf_norm_letter(
        self, letter_page: PageGeometry, xn: float, yn: float, wn: float, hn: float
    ) -> None:
        x0, y0, x1, y1 = rect_norm_to_pdf(xn, yn, wn, hn, letter_page)
        rxn, ryn, rwn, rhn = rect_pdf_to_norm(x0, y0, x1, y1, letter_page)
        assert rxn == pytest.approx(xn, abs=1e-9)
        assert ryn == pytest.approx(yn, abs=1e-9)
        assert rwn == pytest.approx(wn, abs=1e-9)
        assert rhn == pytest.approx(hn, abs=1e-9)

    def test_roundtrip_a4(self, a4_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(50, 100, 400, 700, a4_page)
        x0, y0, x1, y1 = rect_norm_to_pdf(xn, yn, wn, hn, a4_page)
        assert x0 == pytest.approx(50.0, abs=1e-9)
        assert y0 == pytest.approx(100.0, abs=1e-9)
        assert x1 == pytest.approx(400.0, abs=1e-9)
        assert y1 == pytest.approx(700.0, abs=1e-9)

    def test_roundtrip_a3(self, a3_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(100, 200, 600, 900, a3_page)
        x0, y0, x1, y1 = rect_norm_to_pdf(xn, yn, wn, hn, a3_page)
        assert x0 == pytest.approx(100.0, abs=1e-9)
        assert y0 == pytest.approx(200.0, abs=1e-9)
        assert x1 == pytest.approx(600.0, abs=1e-9)
        assert y1 == pytest.approx(900.0, abs=1e-9)

    def test_roundtrip_square(self, square_page: PageGeometry) -> None:
        xn, yn, wn, hn = rect_pdf_to_norm(50, 50, 450, 450, square_page)
        x0, y0, x1, y1 = rect_norm_to_pdf(xn, yn, wn, hn, square_page)
        assert x0 == pytest.approx(50.0, abs=1e-9)
        assert y0 == pytest.approx(50.0, abs=1e-9)
        assert x1 == pytest.approx(450.0, abs=1e-9)
        assert y1 == pytest.approx(450.0, abs=1e-9)

    @pytest.mark.parametrize("rot", [0, 90, 180, 270])
    def test_roundtrip_all_rotations(self, rot: int) -> None:
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792, rotation=rot)
        ew = page.effective_width_pt
        eh = page.effective_height_pt
        # Pick a rect in the center 50%
        x0, y0, x1, y1 = ew * 0.25, eh * 0.25, ew * 0.75, eh * 0.75
        xn, yn, wn, hn = rect_pdf_to_norm(x0, y0, x1, y1, page)
        rx0, ry0, rx1, ry1 = rect_norm_to_pdf(xn, yn, wn, hn, page)
        assert rx0 == pytest.approx(x0, abs=1e-9)
        assert ry0 == pytest.approx(y0, abs=1e-9)
        assert rx1 == pytest.approx(x1, abs=1e-9)
        assert ry1 == pytest.approx(y1, abs=1e-9)


# ====================================================================
# 6. DPI-based pixel round-trip tests
# ====================================================================


class TestDpiPixelRoundTrip:
    """Verify that converting via pixel coords (at various DPIs) is consistent."""

    @pytest.mark.parametrize("dpi", [72, 96, 150, 300])
    def test_pixel_to_norm_via_point(self, dpi: int) -> None:
        """Simulate: pixel coords at *dpi* -> PDF points -> normalised."""
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792)

        # A pixel coordinate at the given DPI
        px_x, px_y = 100.0, 200.0
        # Convert to points:  pt = px * 72 / dpi
        x_pt = px_x * 72.0 / dpi
        y_pt = px_y * 72.0 / dpi

        xn, yn = point_pdf_to_norm(x_pt, y_pt, page)
        assert 0.0 <= xn <= 1.0
        assert 0.0 <= yn <= 1.0

    @pytest.mark.parametrize("dpi", [72, 150, 300])
    def test_rect_pixel_roundtrip(self, dpi: int) -> None:
        """pixel -> pt -> norm -> pt -> pixel should be identity."""
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792)

        # Pixel rect
        px0, py0, px1, py1 = 50.0, 80.0, 400.0, 600.0
        # To points
        scale = 72.0 / dpi
        x0 = px0 * scale
        y0 = py0 * scale
        x1 = px1 * scale
        y1 = py1 * scale

        xn, yn, wn, hn = rect_pdf_to_norm(x0, y0, x1, y1, page)
        rx0, ry0, rx1, ry1 = rect_norm_to_pdf(xn, yn, wn, hn, page)

        # Back to pixels
        rpx0 = rx0 / scale
        rpy0 = ry0 / scale
        rpx1 = rx1 / scale
        rpy1 = ry1 / scale

        assert rpx0 == pytest.approx(px0, abs=1e-6)
        assert rpy0 == pytest.approx(py0, abs=1e-6)
        assert rpx1 == pytest.approx(px1, abs=1e-6)
        assert rpy1 == pytest.approx(py1, abs=1e-6)


# ====================================================================
# 7. Stress / edge-case combos
# ====================================================================


class TestEdgeCombinations:
    """Unusual but valid configurations."""

    def test_very_wide_page(self) -> None:
        """Banner-like PDF: very wide, very short."""
        page = PageGeometry(page_number=1, width_pt=2000, height_pt=50)
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, 2000, 50, page)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)

    def test_very_tall_page(self) -> None:
        """Receipt-like PDF: very narrow, very tall."""
        page = PageGeometry(page_number=1, width_pt=200, height_pt=5000)
        xn, yn = point_pdf_to_norm(100, 2500, page)
        assert xn == pytest.approx(0.5)
        assert yn == pytest.approx(0.5)

    def test_fractional_dimensions(self) -> None:
        """Non-integer page dimensions (common with metric page sizes)."""
        page = PageGeometry(page_number=1, width_pt=595.276, height_pt=841.89)
        xn, yn, wn, hn = rect_pdf_to_norm(
            0, 0, 595.276, 841.89, page
        )
        assert wn == pytest.approx(1.0, abs=1e-9)
        assert hn == pytest.approx(1.0, abs=1e-9)

    def test_rect_on_boundary(self, letter_page: PageGeometry) -> None:
        """Rect touching all four edges."""
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, LETTER_W, LETTER_H, letter_page)
        x0, y0, x1, y1 = rect_norm_to_pdf(xn, yn, wn, hn, letter_page)
        assert x0 == pytest.approx(0.0)
        assert y0 == pytest.approx(0.0)
        assert x1 == pytest.approx(LETTER_W)
        assert y1 == pytest.approx(LETTER_H)

    def test_one_pixel_rect_high_dpi(self) -> None:
        """1 pixel at 300 DPI = 72/300 = 0.24 points."""
        page = PageGeometry(page_number=1, width_pt=612, height_pt=792)
        one_px_pt = 72.0 / 300.0
        xn, yn, wn, hn = rect_pdf_to_norm(
            100, 100, 100 + one_px_pt, 100 + one_px_pt, page
        )
        assert wn > 0
        assert hn > 0
        # Round-trip
        rx0, ry0, rx1, ry1 = rect_norm_to_pdf(xn, yn, wn, hn, page)
        assert rx1 - rx0 == pytest.approx(one_px_pt, abs=1e-9)
        assert ry1 - ry0 == pytest.approx(one_px_pt, abs=1e-9)

    def test_high_page_number(self) -> None:
        """Ensure page_number doesn't affect geometry."""
        page = PageGeometry(page_number=9999, width_pt=612, height_pt=792)
        xn, yn = point_pdf_to_norm(306, 396, page)
        assert xn == pytest.approx(0.5)
        assert yn == pytest.approx(0.5)

    def test_custom_tiny_page(self) -> None:
        """Postage-stamp-sized page."""
        page = PageGeometry(page_number=1, width_pt=36, height_pt=36)  # 0.5 in
        xn, yn = point_pdf_to_norm(18, 18, page)
        assert xn == pytest.approx(0.5)
        assert yn == pytest.approx(0.5)

    def test_custom_large_page(self) -> None:
        """Poster-sized page (36x48 in)."""
        page = PageGeometry(page_number=1, width_pt=2592, height_pt=3456)
        xn, yn, wn, hn = rect_pdf_to_norm(0, 0, 2592, 3456, page)
        assert wn == pytest.approx(1.0)
        assert hn == pytest.approx(1.0)
