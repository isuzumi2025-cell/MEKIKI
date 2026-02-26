"""
Coordinate event logging middleware.

Logs raw coordinates from both PDF and Web overlays for diagnostics
and debugging of coordinate mismatches between the two views.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def log_coordinate_event(
    source: str,
    page: int,
    coords: Dict[str, float],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log a coordinate event from either PDF or Web overlay.

    Args:
        source: Origin of the coordinate event ("pdf" or "web").
        page: 1-based page number.
        coords: Dictionary with coordinate values (e.g. x, y, x1, y1, x2, y2).
        meta: Optional metadata (zoom level, rotation, viewport info, etc.).

    Returns:
        The structured log entry that was emitted.
    """
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "page": page,
        "coords": coords,
        "meta": meta or {},
    }
    logger.info(json.dumps(entry, ensure_ascii=False))
    return entry


def log_coordinate_comparison(
    page: int,
    pdf_coords: Dict[str, float],
    web_coords: Dict[str, float],
    delta: Dict[str, float],
    tolerance: float,
    passed: bool,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log a coordinate comparison result between PDF and Web views.

    Args:
        page: 1-based page number.
        pdf_coords: Coordinates from PDF view.
        web_coords: Coordinates from Web view.
        delta: Computed differences for each axis.
        tolerance: Maximum allowed difference in PDF points.
        passed: Whether the comparison passed within tolerance.
        meta: Optional metadata (zoom, rotation, etc.).

    Returns:
        The structured comparison log entry.
    """
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "coordinate_comparison",
        "page": page,
        "pdf_coords": pdf_coords,
        "web_coords": web_coords,
        "delta": delta,
        "tolerance": tolerance,
        "passed": passed,
        "meta": meta or {},
    }
    level = logging.INFO if passed else logging.WARNING
    logger.log(level, json.dumps(entry, ensure_ascii=False))
    return entry


def collect_coordinate_events(
    entries: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group logged coordinate entries by source.

    Args:
        entries: List of coordinate log entries.

    Returns:
        Dictionary mapping source ("pdf"/"web") to list of entries.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {"pdf": [], "web": []}
    for entry in entries:
        source = entry.get("source", "unknown")
        if source not in grouped:
            grouped[source] = []
        grouped[source].append(entry)
    return grouped
