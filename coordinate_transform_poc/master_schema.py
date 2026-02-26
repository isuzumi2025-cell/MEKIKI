"""
Master Coordinate Schema

Defines the canonical print-space coordinate system used as the single
source of truth for all geometry in MEKIKI.  Every device-specific
representation is derived from this master space via an affine transform.

Units
-----
The master space uses millimetres (mm) by default.  Conversion helpers
are provided for points (pt, 1 pt = 25.4/72 mm) and inches
(1 in = 25.4 mm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

class Unit(Enum):
    MM = "mm"
    PT = "pt"
    INCH = "in"


# Conversion factors → mm
_TO_MM = {
    Unit.MM: 1.0,
    Unit.PT: 25.4 / 72.0,   # 1 pt ≈ 0.3528 mm
    Unit.INCH: 25.4,
}


def to_mm(value: float, unit: Unit) -> float:
    """Convert *value* in *unit* to millimetres."""
    return value * _TO_MM[unit]


def from_mm(value_mm: float, unit: Unit) -> float:
    """Convert a millimetre value to *unit*."""
    return value_mm / _TO_MM[unit]


# ---------------------------------------------------------------------------
# Core geometry types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point2D:
    """An immutable 2-D point in master (mm) space."""
    x: float
    y: float

    def to_array(self) -> np.ndarray:
        """Return as a homogeneous column vector [x, y, 1]."""
        return np.array([self.x, self.y, 1.0], dtype=np.float64)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Point2D":
        """Construct from a homogeneous vector [x, y, ...]."""
        return cls(x=float(arr[0]), y=float(arr[1]))

    def distance_to(self, other: "Point2D") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in master space (mm)."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError(
                f"Invalid bbox: min must be <= max, got "
                f"({self.x_min}, {self.y_min}) -> ({self.x_max}, {self.y_max})"
            )

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> Point2D:
        return Point2D(
            x=(self.x_min + self.x_max) / 2.0,
            y=(self.y_min + self.y_max) / 2.0,
        )

    def corners(self) -> List[Point2D]:
        """Return the four corners (TL, TR, BR, BL)."""
        return [
            Point2D(self.x_min, self.y_min),
            Point2D(self.x_max, self.y_min),
            Point2D(self.x_max, self.y_max),
            Point2D(self.x_min, self.y_max),
        ]


# ---------------------------------------------------------------------------
# 3 x 3 affine transform matrix
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransformMatrix:
    """Row-major 3x3 affine matrix.

    | a  b  c |     | sx * cos(θ)  -sy * sin(θ)   tx |
    | d  e  f |  =  | sx * sin(θ)   sy * cos(θ)   ty |
    | g  h  i |     | 0             0              1  |
    """
    a: float
    b: float
    c: float  # tx
    d: float
    e: float
    f: float  # ty
    g: float = 0.0
    h: float = 0.0
    i: float = 1.0

    # ---- numpy interop ----

    def to_ndarray(self) -> np.ndarray:
        """Return a (3, 3) float64 numpy array."""
        return np.array([
            [self.a, self.b, self.c],
            [self.d, self.e, self.f],
            [self.g, self.h, self.i],
        ], dtype=np.float64)

    @classmethod
    def from_ndarray(cls, m: np.ndarray) -> "TransformMatrix":
        return cls(
            a=float(m[0, 0]), b=float(m[0, 1]), c=float(m[0, 2]),
            d=float(m[1, 0]), e=float(m[1, 1]), f=float(m[1, 2]),
            g=float(m[2, 0]), h=float(m[2, 1]), i=float(m[2, 2]),
        )

    # ---- constructors ----

    @classmethod
    def identity(cls) -> "TransformMatrix":
        return cls(1.0, 0.0, 0.0,
                   0.0, 1.0, 0.0)

    @classmethod
    def scale(cls, sx: float, sy: float) -> "TransformMatrix":
        return cls(sx, 0.0, 0.0,
                   0.0, sy, 0.0)

    @classmethod
    def translate(cls, tx: float, ty: float) -> "TransformMatrix":
        return cls(1.0, 0.0, tx,
                   0.0, 1.0, ty)

    @classmethod
    def rotate(cls, angle_deg: float) -> "TransformMatrix":
        rad = math.radians(angle_deg)
        c_ = math.cos(rad)
        s_ = math.sin(rad)
        return cls(c_, -s_, 0.0,
                   s_,  c_, 0.0)

    @classmethod
    def compose(cls, *matrices: "TransformMatrix") -> "TransformMatrix":
        """Compose transforms left-to-right (first applied first)."""
        result = np.eye(3, dtype=np.float64)
        for m in matrices:
            result = m.to_ndarray() @ result
        return cls.from_ndarray(result)

    # ---- operations ----

    def inverse(self) -> "TransformMatrix":
        m = self.to_ndarray()
        inv = np.linalg.inv(m)
        return TransformMatrix.from_ndarray(inv)

    def apply(self, pt: Point2D) -> Point2D:
        """Transform a single point (scalar path)."""
        x = self.a * pt.x + self.b * pt.y + self.c
        y = self.d * pt.x + self.e * pt.y + self.f
        return Point2D(x, y)

    def apply_batch(self, points: np.ndarray) -> np.ndarray:
        """Transform an (N, 2) array of points using NumPy.

        Returns an (N, 2) float64 array.
        """
        n = points.shape[0]
        ones = np.ones((n, 1), dtype=np.float64)
        homo = np.hstack([points.astype(np.float64), ones])  # (N, 3)
        m = self.to_ndarray()  # (3, 3)
        result = (m @ homo.T).T  # (N, 3)
        return result[:, :2]

    def determinant(self) -> float:
        return float(np.linalg.det(self.to_ndarray()))


# ---------------------------------------------------------------------------
# Master coordinate space container
# ---------------------------------------------------------------------------

@dataclass
class MasterCoordinateSpace:
    """Top-level container describing the master print-space."""
    unit: Unit
    dpi: float            # target print resolution
    origin: Point2D       # master origin (usually 0,0)
    page_width_mm: float  # e.g. 420.0 for A3
    page_height_mm: float # e.g. 297.0 for A3

    @property
    def page_width_px(self) -> float:
        """Width expressed in device dots at *self.dpi*."""
        return self.page_width_mm / 25.4 * self.dpi

    @property
    def page_height_px(self) -> float:
        return self.page_height_mm / 25.4 * self.dpi


__all__ = [
    "Unit", "to_mm", "from_mm",
    "Point2D", "BBox", "TransformMatrix",
    "MasterCoordinateSpace",
]
