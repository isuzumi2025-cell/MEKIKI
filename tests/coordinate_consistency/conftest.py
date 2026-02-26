"""
Shared fixtures for coordinate consistency tests.

Provides reusable page metadata, known element fixtures, zoom/rotation
parameter matrices, and tolerance constants.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default tolerance in PDF points (1 pt = 1/72 inch).
#: 0.5 pt ~= 0.18 mm, tight enough for proofing yet forgiving of float errors.
DEFAULT_TOLERANCE_PT = 0.5

#: DPI scale used when converting between PDF points and image pixels.
DPI_SCALE = 300.0 / 72.0  # ~4.1667


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageMeta:
    """Metadata for a single PDF page."""

    width: float   # PDF points
    height: float  # PDF points
    rotation: int  # 0, 90, 180, 270


@dataclass(frozen=True)
class CanonicalPoint:
    """A point in PDF coordinate space (origin: bottom-left)."""

    x: float  # PDF points
    y: float  # PDF points
    page: int  # 1-based


@dataclass(frozen=True)
class WebPoint:
    """A point in CSS-pixel coordinate space (origin: top-left)."""

    x: float  # CSS pixels
    y: float  # CSS pixels
    page: int  # 1-based


@dataclass(frozen=True)
class KnownElement:
    """A known element with its expected PDF and Web coordinates."""

    name: str
    pdf_point: CanonicalPoint
    page_meta: PageMeta


# ---------------------------------------------------------------------------
# Coordinate conversion functions (Python reference implementation)
# ---------------------------------------------------------------------------

def effective_page_size(meta: PageMeta) -> Tuple[float, float]:
    """Return (width, height) after applying rotation."""
    if meta.rotation in (90, 270):
        return (meta.height, meta.width)
    return (meta.width, meta.height)


def apply_rotation(x: float, y: float, meta: PageMeta) -> Tuple[float, float]:
    """Rotate a canonical point according to page rotation."""
    w, h = meta.width, meta.height
    if meta.rotation == 0:
        return (x, y)
    if meta.rotation == 90:
        return (y, w - x)
    if meta.rotation == 180:
        return (w - x, h - y)
    if meta.rotation == 270:
        return (h - y, x)
    return (x, y)


def reverse_rotation(
    x: float, y: float, meta: PageMeta
) -> Tuple[float, float]:
    """Reverse page rotation to recover canonical coordinates."""
    w, h = meta.width, meta.height
    if meta.rotation == 0:
        return (x, y)
    if meta.rotation == 90:
        return (w - y, x)
    if meta.rotation == 180:
        return (w - x, h - y)
    if meta.rotation == 270:
        return (y, h - x)
    return (x, y)


def pdf_to_web(
    point: CanonicalPoint,
    meta: PageMeta,
    viewport_scale: float,
    dpi_scale: float,
) -> WebPoint:
    """Convert canonical PDF point to CSS-pixel Web point."""
    rx, ry = apply_rotation(point.x, point.y, meta)
    eff_w, eff_h = effective_page_size(meta)
    return WebPoint(
        x=rx * viewport_scale * dpi_scale,
        y=(eff_h - ry) * viewport_scale * dpi_scale,
        page=point.page,
    )


def web_to_pdf(
    point: WebPoint,
    meta: PageMeta,
    viewport_scale: float,
    dpi_scale: float,
) -> CanonicalPoint:
    """Convert CSS-pixel Web point back to canonical PDF point."""
    scale = viewport_scale * dpi_scale
    eff_w, eff_h = effective_page_size(meta)
    rx = point.x / scale
    ry = eff_h - point.y / scale
    ux, uy = reverse_rotation(rx, ry, meta)
    return CanonicalPoint(x=ux, y=uy, page=point.page)


def point_distance(a: CanonicalPoint, b: CanonicalPoint) -> float:
    """Euclidean distance between two canonical points (PDF points)."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Common page sizes in PDF points (72 pt/inch).
PAGE_SIZES: Dict[str, Tuple[float, float]] = {
    "A4_portrait":  (595.28, 841.89),
    "A4_landscape": (841.89, 595.28),
    "A3_portrait":  (841.89, 1190.55),
    "Letter":       (612.0,  792.0),
    "Tabloid":      (792.0,  1224.0),
    "B5":           (498.90, 708.66),
    "custom_small": (300.0,  400.0),
    "custom_wide":  (1000.0, 500.0),
}

ROTATIONS: List[int] = [0, 90, 180, 270]

ZOOM_LEVELS: List[float] = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]

DPI_SCALES: List[float] = [1.0, 1.5, 2.0, 3.0]


@pytest.fixture(params=list(PAGE_SIZES.keys()), ids=lambda k: f"page={k}")
def page_size_name(request: pytest.FixtureRequest) -> str:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def page_size(page_size_name: str) -> Tuple[float, float]:
    return PAGE_SIZES[page_size_name]


@pytest.fixture(params=ROTATIONS, ids=lambda r: f"rot={r}")
def rotation(request: pytest.FixtureRequest) -> int:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=ZOOM_LEVELS, ids=lambda z: f"zoom={z}")
def zoom(request: pytest.FixtureRequest) -> float:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(params=DPI_SCALES, ids=lambda d: f"dpi={d}")
def dpi_scale(request: pytest.FixtureRequest) -> float:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture
def page_meta(page_size: Tuple[float, float], rotation: int) -> PageMeta:
    """Build a PageMeta for every (page_size, rotation) combination."""
    return PageMeta(width=page_size[0], height=page_size[1], rotation=rotation)


def _make_known_elements(meta: PageMeta) -> List[KnownElement]:
    """
    Generate a set of known reference elements spread across the page.

    Positions cover corners, edges, and interior points to exercise
    every quadrant of the coordinate space.
    """
    w, h = meta.width, meta.height
    margin = min(w, h) * 0.05  # 5% margin from edges

    positions = {
        "top_left":      (margin, h - margin),
        "top_right":     (w - margin, h - margin),
        "bottom_left":   (margin, margin),
        "bottom_right":  (w - margin, margin),
        "center":        (w / 2, h / 2),
        "mid_top":       (w / 2, h - margin),
        "mid_bottom":    (w / 2, margin),
        "mid_left":      (margin, h / 2),
        "mid_right":     (w - margin, h / 2),
        "quarter_nw":    (w * 0.25, h * 0.75),
        "quarter_ne":    (w * 0.75, h * 0.75),
        "quarter_sw":    (w * 0.25, h * 0.25),
        "quarter_se":    (w * 0.75, h * 0.25),
    }

    return [
        KnownElement(
            name=name,
            pdf_point=CanonicalPoint(x=x, y=y, page=1),
            page_meta=meta,
        )
        for name, (x, y) in positions.items()
    ]


@pytest.fixture
def known_elements(page_meta: PageMeta) -> List[KnownElement]:
    """Known reference elements for the current page geometry."""
    return _make_known_elements(page_meta)
