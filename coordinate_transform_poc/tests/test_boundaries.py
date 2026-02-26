"""
Boundary / worst-case value tests.

Ensures the transformation pipeline handles extreme coordinate values
gracefully and reports expected errors.
"""

from __future__ import annotations

import math
import sys

import numpy as np
import pytest

from coordinate_transform_poc.boundary_tests import (
    get_boundary_test_cases,
    run_boundary_tests,
)
from coordinate_transform_poc.device_registry import PRINTER_A3_300, create_default_registry
from coordinate_transform_poc.master_schema import MasterCoordinateSpace, Point2D, Unit
from coordinate_transform_poc.transform_pipeline import BatchPipeline


@pytest.fixture
def master() -> MasterCoordinateSpace:
    return MasterCoordinateSpace(
        unit=Unit.MM, dpi=300.0,
        origin=Point2D(0.0, 0.0),
        page_width_mm=420.0, page_height_mm=297.0,
    )


# ---------------------------------------------------------------------------
# Individual boundary category tests
# ---------------------------------------------------------------------------

class TestTypicalPrint:
    """Normal A4/A3 coordinates should round-trip perfectly in float64."""

    def test_a4_corner(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[210.0, 297.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-10

    def test_origin(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[0.0, 0.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) == 0.0


class TestVeryLargeCoords:
    """Coordinates far beyond typical print (billboard scale)."""

    def test_10m(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[10_000.0, 10_000.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-7

    def test_100m(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[100_000.0, 100_000.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-5


class TestSubMicronCoords:
    """Very small coordinates testing precision floor."""

    def test_nanometre(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[1e-6, 1e-6]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-15

    def test_picometre(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[1e-9, 1e-9]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-15


class TestNegativeCoords:
    """Bleed / trim zones with negative coordinates."""

    def test_small_bleed(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[-3.0, -3.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-10

    def test_large_negative(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[-1e6, -1e6]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-4


class TestMixedMagnitude:
    """One axis tiny, one axis huge."""

    def test_mixed(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[1e-10, 1e10], [1e10, 1e-10]])
        _, err = pipe.round_trip(pts)
        # Relative to the large axis, error should be tiny
        assert float(np.max(err)) < 1e-2


class TestIrrationalCoords:
    """Non-representable fractions and irrationals."""

    def test_pi_and_e(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[math.pi, math.e]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-10

    def test_repeating_decimal(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[1.0 / 3.0, 1.0 / 7.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 1e-10


class TestFloat32Boundaries:
    """float32 boundary behaviour."""

    def test_typical_coords_f32(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float32)
        pts = np.array([[210.0, 297.0], [420.0, 297.0]])
        _, err = pipe.round_trip(pts)
        assert float(np.max(err)) < 0.01

    def test_large_coords_f32_degrades(self, master: MasterCoordinateSpace) -> None:
        """float32 should show worse accuracy for large coords."""
        pipe32 = BatchPipeline(master, PRINTER_A3_300, dtype=np.float32)
        pipe64 = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        pts = np.array([[50_000.0, 50_000.0]])
        _, err32 = pipe32.round_trip(pts)
        _, err64 = pipe64.round_trip(pts)
        # float32 error should be measurably larger
        assert float(np.max(err32)) >= float(np.max(err64))


# ---------------------------------------------------------------------------
# Full boundary suite
# ---------------------------------------------------------------------------

class TestFullBoundarySuite:
    def test_all_boundary_cases_run(self) -> None:
        """The full suite should execute without exceptions."""
        results = run_boundary_tests()
        assert len(results) > 0

    def test_typical_print_all_pass(self) -> None:
        results = run_boundary_tests()
        typical = [r for r in results if r.case_name == "typical_print"]
        assert all(r.passed for r in typical), (
            "Typical print cases should all pass: "
            + str([(r.device_name, r.dtype_name, r.notes) for r in typical if not r.passed])
        )

    def test_no_nan_in_normal_cases(self) -> None:
        results = run_boundary_tests()
        normal_cases = {"typical_print", "negative_coords", "dpr_stress"}
        normal = [r for r in results if r.case_name in normal_cases]
        assert not any(r.any_nan for r in normal)
