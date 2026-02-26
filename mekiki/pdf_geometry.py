"""
PDF page geometry utilities.

Stores page dimensions in PDF user-space points (1 pt = 1/72 inch)
and provides helpers for DPI-based pixel conversion and rotation handling.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageGeometry:
    """Immutable description of a single PDF page's geometry.

    Parameters
    ----------
    page_number : int
        1-based page number inside the document.
    width_pt : float
        *Un-rotated* page width in PDF points.
    height_pt : float
        *Un-rotated* page height in PDF points.
    rotation : int
        Clock-wise rotation applied to the page (0, 90, 180, 270).
    """

    page_number: int
    width_pt: float
    height_pt: float
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.width_pt <= 0:
            raise ValueError(f"width_pt must be positive, got {self.width_pt}")
        if self.height_pt <= 0:
            raise ValueError(f"height_pt must be positive, got {self.height_pt}")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError(
                f"rotation must be 0, 90, 180 or 270, got {self.rotation}"
            )

    # ------------------------------------------------------------------
    # Effective (rotated) dimensions
    # ------------------------------------------------------------------

    @property
    def effective_width_pt(self) -> float:
        """Width after applying *rotation*."""
        if self.rotation in (90, 270):
            return self.height_pt
        return self.width_pt

    @property
    def effective_height_pt(self) -> float:
        """Height after applying *rotation*."""
        if self.rotation in (90, 270):
            return self.width_pt
        return self.height_pt

    # ------------------------------------------------------------------
    # Pixel helpers
    # ------------------------------------------------------------------

    def width_px(self, dpi: float = 72.0) -> float:
        """Effective width in pixels at the given *dpi*."""
        return self.effective_width_pt * dpi / 72.0

    def height_px(self, dpi: float = 72.0) -> float:
        """Effective height in pixels at the given *dpi*."""
        return self.effective_height_pt * dpi / 72.0
