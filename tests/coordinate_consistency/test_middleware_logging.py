"""
Tests for the coordinate logging middleware.

Verify that log entries are structured correctly and that the
comparison logger produces valid pass/fail outputs.
"""

import json

import pytest

from middleware.logging import (
    collect_coordinate_events,
    log_coordinate_comparison,
    log_coordinate_event,
)


class TestLogCoordinateEvent:
    """Verify log_coordinate_event produces structured entries."""

    def test_basic_pdf_event(self) -> None:
        entry = log_coordinate_event(
            source="pdf",
            page=1,
            coords={"x": 100.0, "y": 200.0},
        )
        assert entry["source"] == "pdf"
        assert entry["page"] == 1
        assert entry["coords"]["x"] == 100.0
        assert entry["coords"]["y"] == 200.0
        assert "timestamp" in entry

    def test_web_event_with_meta(self) -> None:
        entry = log_coordinate_event(
            source="web",
            page=2,
            coords={"x": 50.5, "y": 75.3},
            meta={"zoom": 1.5, "rotation": 90},
        )
        assert entry["source"] == "web"
        assert entry["page"] == 2
        assert entry["meta"]["zoom"] == 1.5
        assert entry["meta"]["rotation"] == 90

    def test_entry_is_json_serializable(self) -> None:
        entry = log_coordinate_event(
            source="pdf",
            page=1,
            coords={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
            meta={"dpi": 300},
        )
        serialized = json.dumps(entry)
        parsed = json.loads(serialized)
        assert parsed["source"] == "pdf"

    def test_none_meta_defaults_to_empty(self) -> None:
        entry = log_coordinate_event(
            source="pdf", page=1, coords={"x": 0, "y": 0}
        )
        assert entry["meta"] == {}


class TestLogCoordinateComparison:
    """Verify comparison logging captures pass/fail state."""

    def test_passing_comparison(self) -> None:
        entry = log_coordinate_comparison(
            page=1,
            pdf_coords={"x": 100.0, "y": 200.0},
            web_coords={"x": 100.1, "y": 200.1},
            delta={"x": 0.1, "y": 0.1},
            tolerance=1.0,
            passed=True,
        )
        assert entry["passed"] is True
        assert entry["tolerance"] == 1.0
        assert entry["type"] == "coordinate_comparison"

    def test_failing_comparison(self) -> None:
        entry = log_coordinate_comparison(
            page=1,
            pdf_coords={"x": 100.0, "y": 200.0},
            web_coords={"x": 105.0, "y": 210.0},
            delta={"x": 5.0, "y": 10.0},
            tolerance=1.0,
            passed=False,
        )
        assert entry["passed"] is False

    def test_comparison_with_meta(self) -> None:
        entry = log_coordinate_comparison(
            page=3,
            pdf_coords={"x": 50.0, "y": 60.0},
            web_coords={"x": 50.0, "y": 60.0},
            delta={"x": 0.0, "y": 0.0},
            tolerance=0.5,
            passed=True,
            meta={"zoom": 2.0, "rotation": 180},
        )
        assert entry["meta"]["zoom"] == 2.0
        assert entry["page"] == 3


class TestCollectCoordinateEvents:
    """Verify event collection and grouping."""

    def test_groups_by_source(self) -> None:
        entries = [
            {"source": "pdf", "page": 1, "coords": {"x": 10}},
            {"source": "web", "page": 1, "coords": {"x": 10}},
            {"source": "pdf", "page": 2, "coords": {"x": 20}},
            {"source": "web", "page": 2, "coords": {"x": 20}},
        ]
        grouped = collect_coordinate_events(entries)
        assert len(grouped["pdf"]) == 2
        assert len(grouped["web"]) == 2

    def test_empty_input(self) -> None:
        grouped = collect_coordinate_events([])
        assert grouped["pdf"] == []
        assert grouped["web"] == []

    def test_unknown_source(self) -> None:
        entries = [{"source": "canvas", "page": 1, "coords": {"x": 5}}]
        grouped = collect_coordinate_events(entries)
        assert "canvas" in grouped
        assert len(grouped["canvas"]) == 1
