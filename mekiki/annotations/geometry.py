"""
Coordinate conversion between PDF user-space and normalised (0-1) space.

The canonical pipeline is::

    PDF user space (points) -> Normalised (0-1) -> Canvas CSS pixels -> Screen pixels

All persistent storage uses normalised coordinates so that rendering is
independent of zoom level, DPI, or device pixel ratio.

Rotation handling
-----------------
PDF pages may carry a ``/Rotate`` value of 0, 90, 180 or 270 degrees
(clockwise).  The conversion helpers use the *effective* (post-rotation)
page dimensions exposed by :class:`~mekiki.pdf_geometry.PageGeometry` so
that normalised coordinates always map to the visual layout the user sees.
"""

from __future__ import annotations

from typing import Tuple

from mekiki.pdf_geometry import PageGeometry


# ------------------------------------------------------------------ #
#  Point conversion
# ------------------------------------------------------------------ #

def point_pdf_to_norm(
    x_pt: float,
    y_pt: float,
    page: PageGeometry,
) -> Tuple[float, float]:
    """Convert a point from PDF user-space to normalised (0-1) coordinates.

    PDF origin is **bottom-left**; normalised origin is **top-left**.

    Parameters
    ----------
    x_pt, y_pt:
        Coordinates in PDF points (bottom-left origin).
    page:
        Page geometry (carries effective dimensions after rotation).

    Returns
    -------
    (x_norm, y_norm) both in [0, 1].

    Raises
    ------
    ValueError
        If *x_pt* or *y_pt* fall outside the page bounds.
    """
    w = page.effective_width_pt
    h = page.effective_height_pt

    if x_pt < 0 or x_pt > w:
        raise ValueError(
            f"x_pt={x_pt} outside page width [0, {w}]"
        )
    if y_pt < 0 or y_pt > h:
        raise ValueError(
            f"y_pt={y_pt} outside page height [0, {h}]"
        )

    x_norm = x_pt / w
    # Flip Y: PDF bottom-left -> normalised top-left
    y_norm = 1.0 - (y_pt / h)
    return (x_norm, y_norm)


# ------------------------------------------------------------------ #
#  Rectangle conversions
# ------------------------------------------------------------------ #

def rect_pdf_to_norm(
    x0_pt: float,
    y0_pt: float,
    x1_pt: float,
    y1_pt: float,
    page: PageGeometry,
) -> Tuple[float, float, float, float]:
    """Convert a rectangle from PDF user-space to normalised coordinates.

    The input rectangle is given as ``(x0, y0, x1, y1)`` in PDF points
    (bottom-left origin).  ``(x0, y0)`` is the *lower-left* corner and
    ``(x1, y1)`` is the *upper-right* corner — the standard PDF convention.

    Returns ``(x_norm, y_norm, w_norm, h_norm)`` where ``(x_norm, y_norm)``
    is the *top-left* corner in normalised space and ``w_norm / h_norm`` are
    the width and height fractions.

    Raises
    ------
    ValueError
        If corners are inverted (``x0 > x1`` or ``y0 > y1``) or
        coordinates fall outside the page.
    """
    if x0_pt > x1_pt:
        raise ValueError(
            f"Inverted x: x0_pt={x0_pt} > x1_pt={x1_pt}"
        )
    if y0_pt > y1_pt:
        raise ValueError(
            f"Inverted y: y0_pt={y0_pt} > y1_pt={y1_pt}"
        )

    w = page.effective_width_pt
    h = page.effective_height_pt

    if x0_pt < 0 or x1_pt > w:
        raise ValueError(
            f"Rectangle x-range [{x0_pt}, {x1_pt}] outside page width [0, {w}]"
        )
    if y0_pt < 0 or y1_pt > h:
        raise ValueError(
            f"Rectangle y-range [{y0_pt}, {y1_pt}] outside page height [0, {h}]"
        )

    x_norm = x0_pt / w
    # Top-left Y in normalised space (flip the upper-right PDF Y)
    y_norm = 1.0 - (y1_pt / h)
    w_norm = (x1_pt - x0_pt) / w
    h_norm = (y1_pt - y0_pt) / h

    return (x_norm, y_norm, w_norm, h_norm)


def rect_norm_to_pdf(
    x_norm: float,
    y_norm: float,
    w_norm: float,
    h_norm: float,
    page: PageGeometry,
) -> Tuple[float, float, float, float]:
    """Convert a normalised rectangle back to PDF user-space points.

    Input ``(x_norm, y_norm)`` is the **top-left** corner in normalised
    (0-1) space.  Returns ``(x0_pt, y0_pt, x1_pt, y1_pt)`` with
    ``(x0, y0)`` being the PDF **lower-left** and ``(x1, y1)`` the
    **upper-right** corner.

    Raises
    ------
    ValueError
        If any normalised value falls outside [0, 1] or the rect
        extends beyond the page.
    """
    for name, val in [
        ("x_norm", x_norm),
        ("y_norm", y_norm),
        ("w_norm", w_norm),
        ("h_norm", h_norm),
    ]:
        if val < 0.0 or val > 1.0:
            raise ValueError(f"{name}={val} outside [0, 1]")

    if x_norm + w_norm > 1.0 + 1e-9:
        raise ValueError(
            f"x_norm + w_norm = {x_norm + w_norm} exceeds 1.0"
        )
    if y_norm + h_norm > 1.0 + 1e-9:
        raise ValueError(
            f"y_norm + h_norm = {y_norm + h_norm} exceeds 1.0"
        )

    w = page.effective_width_pt
    h = page.effective_height_pt

    x0_pt = x_norm * w
    # PDF lower-left Y = flip the bottom edge of the normalised rect
    y0_pt = (1.0 - (y_norm + h_norm)) * h
    x1_pt = (x_norm + w_norm) * w
    y1_pt = (1.0 - y_norm) * h

    return (x0_pt, y0_pt, x1_pt, y1_pt)
