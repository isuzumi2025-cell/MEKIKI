"""
Tests for the core transformation pipeline.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from coordinate_transform_poc.device_registry import (
    HIRES_MONITOR,
    IPAD_PRO_129,
    PRINTER_A3_300,
    create_default_registry,
)
from coordinate_transform_poc.master_schema import (
    BBox,
    MasterCoordinateSpace,
    Point2D,
    TransformMatrix,
    Unit,
    from_mm,
    to_mm,
)
from coordinate_transform_poc.transform_pipeline import (
    BatchPipeline,
    PipelineResult,
    ScalarPipeline,
    build_device_transform,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def master() -> MasterCoordinateSpace:
    return MasterCoordinateSpace(
        unit=Unit.MM,
        dpi=300.0,
        origin=Point2D(0.0, 0.0),
        page_width_mm=420.0,
        page_height_mm=297.0,
    )


# ---------------------------------------------------------------------------
# Unit conversion tests
# ---------------------------------------------------------------------------

class TestUnitConversion:
    def test_mm_identity(self) -> None:
        assert to_mm(100.0, Unit.MM) == 100.0

    def test_pt_to_mm(self) -> None:
        # 72 pt = 1 inch = 25.4 mm
        assert abs(to_mm(72.0, Unit.PT) - 25.4) < 1e-10

    def test_inch_to_mm(self) -> None:
        assert abs(to_mm(1.0, Unit.INCH) - 25.4) < 1e-10

    def test_round_trip_pt(self) -> None:
        val = 123.456
        assert abs(from_mm(to_mm(val, Unit.PT), Unit.PT) - val) < 1e-10


# ---------------------------------------------------------------------------
# Point2D / TransformMatrix tests
# ---------------------------------------------------------------------------

class TestPoint2D:
    def test_to_array_homogeneous(self) -> None:
        p = Point2D(10.0, 20.0)
        arr = p.to_array()
        assert arr.shape == (3,)
        assert arr[2] == 1.0

    def test_from_array(self) -> None:
        arr = np.array([3.14, 2.71, 1.0])
        p = Point2D.from_array(arr)
        assert abs(p.x - 3.14) < 1e-12
        assert abs(p.y - 2.71) < 1e-12

    def test_distance(self) -> None:
        a = Point2D(0.0, 0.0)
        b = Point2D(3.0, 4.0)
        assert abs(a.distance_to(b) - 5.0) < 1e-12


class TestTransformMatrix:
    def test_identity(self) -> None:
        m = TransformMatrix.identity()
        p = Point2D(42.0, 99.0)
        q = m.apply(p)
        assert abs(q.x - p.x) < 1e-12
        assert abs(q.y - p.y) < 1e-12

    def test_scale(self) -> None:
        m = TransformMatrix.scale(2.0, 3.0)
        q = m.apply(Point2D(10.0, 10.0))
        assert abs(q.x - 20.0) < 1e-12
        assert abs(q.y - 30.0) < 1e-12

    def test_translate(self) -> None:
        m = TransformMatrix.translate(5.0, -3.0)
        q = m.apply(Point2D(10.0, 10.0))
        assert abs(q.x - 15.0) < 1e-12
        assert abs(q.y - 7.0) < 1e-12

    def test_rotate_90(self) -> None:
        m = TransformMatrix.rotate(90.0)
        q = m.apply(Point2D(1.0, 0.0))
        assert abs(q.x - 0.0) < 1e-10
        assert abs(q.y - 1.0) < 1e-10

    def test_inverse_round_trip(self) -> None:
        m = TransformMatrix.compose(
            TransformMatrix.scale(2.5, 3.7),
            TransformMatrix.translate(10.0, -20.0),
            TransformMatrix.rotate(37.0),
        )
        inv = m.inverse()
        p = Point2D(123.456, 789.012)
        q = m.apply(p)
        p2 = inv.apply(q)
        assert abs(p.x - p2.x) < 1e-8
        assert abs(p.y - p2.y) < 1e-8

    def test_batch_matches_scalar(self) -> None:
        m = TransformMatrix.compose(
            TransformMatrix.scale(1.5, 2.0),
            TransformMatrix.translate(3.0, 4.0),
        )
        pts = np.array([[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]])
        batch_result = m.apply_batch(pts)
        for i in range(3):
            scalar = m.apply(Point2D(pts[i, 0], pts[i, 1]))
            assert abs(batch_result[i, 0] - scalar.x) < 1e-10
            assert abs(batch_result[i, 1] - scalar.y) < 1e-10

    def test_determinant_identity(self) -> None:
        assert abs(TransformMatrix.identity().determinant() - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# BBox tests
# ---------------------------------------------------------------------------

class TestBBox:
    def test_valid(self) -> None:
        b = BBox(0, 0, 100, 200)
        assert b.width == 100.0
        assert b.height == 200.0

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            BBox(100, 0, 0, 200)

    def test_corners(self) -> None:
        b = BBox(10, 20, 30, 40)
        corners = b.corners()
        assert len(corners) == 4
        assert corners[0] == Point2D(10, 20)
        assert corners[2] == Point2D(30, 40)


# ---------------------------------------------------------------------------
# Scalar pipeline tests
# ---------------------------------------------------------------------------

class TestScalarPipeline:
    def test_forward_origin(self, master: MasterCoordinateSpace) -> None:
        pipe = ScalarPipeline(master, PRINTER_A3_300)
        result = pipe.forward(Point2D(0.0, 0.0))
        assert isinstance(result, PipelineResult)
        final = result.final_output
        assert isinstance(final, Point2D)
        assert abs(final.x) < 1e-10
        assert abs(final.y) < 1e-10

    def test_forward_a3_corner_printer(self, master: MasterCoordinateSpace) -> None:
        """420 mm at 300 DPI → 420/25.4*300 ≈ 4960.63 px."""
        pipe = ScalarPipeline(master, PRINTER_A3_300)
        result = pipe.forward(Point2D(420.0, 297.0))
        final = result.final_output
        assert isinstance(final, Point2D)
        expected_x = 420.0 / 25.4 * 300.0
        expected_y = 297.0 / 25.4 * 300.0
        assert abs(final.x - expected_x) < 1e-6
        assert abs(final.y - expected_y) < 1e-6

    def test_round_trip_scalar(self, master: MasterCoordinateSpace) -> None:
        pipe = ScalarPipeline(master, IPAD_PRO_129)
        original = Point2D(210.0, 148.5)
        fwd = pipe.forward(original)
        fwd_pt = fwd.final_output
        assert isinstance(fwd_pt, Point2D)
        inv = pipe.inverse(fwd_pt)
        inv_pt = inv.final_output
        assert isinstance(inv_pt, Point2D)
        assert abs(original.x - inv_pt.x) < 1e-8
        assert abs(original.y - inv_pt.y) < 1e-8

    def test_stages_have_timing(self, master: MasterCoordinateSpace) -> None:
        pipe = ScalarPipeline(master, HIRES_MONITOR)
        result = pipe.forward(Point2D(100.0, 100.0))
        assert len(result.stages) >= 4
        assert all(s.elapsed_ns >= 0 for s in result.stages)

    def test_css_dpr_reduces_coords(self, master: MasterCoordinateSpace) -> None:
        """With DPR=2, CSS coords should be half the device pixels."""
        pipe = ScalarPipeline(master, IPAD_PRO_129)
        no_dpr = pipe.forward(Point2D(100.0, 100.0), apply_css_dpr=False)
        with_dpr = pipe.forward(Point2D(100.0, 100.0), apply_css_dpr=True)
        no_pt = no_dpr.final_output
        css_pt = with_dpr.final_output
        assert isinstance(no_pt, Point2D)
        assert isinstance(css_pt, Point2D)
        assert abs(css_pt.x - no_pt.x / 2.0) < 1e-6
        assert abs(css_pt.y - no_pt.y / 2.0) < 1e-6


# ---------------------------------------------------------------------------
# Batch pipeline tests
# ---------------------------------------------------------------------------

class TestBatchPipeline:
    def test_forward_batch_shape(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, PRINTER_A3_300)
        pts = np.array([[0.0, 0.0], [420.0, 297.0], [210.0, 148.5]])
        result, _ = pipe.forward(pts)
        assert result.shape == (3, 2)

    def test_round_trip_batch_f64(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, HIRES_MONITOR, dtype=np.float64)
        rng = np.random.default_rng(123)
        pts = rng.uniform(0, 500, (1000, 2))
        _, errors = pipe.round_trip(pts)
        assert np.all(errors < 1e-8)

    def test_round_trip_batch_f32(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, HIRES_MONITOR, dtype=np.float32)
        rng = np.random.default_rng(123)
        pts = rng.uniform(0, 500, (1000, 2))
        _, errors = pipe.round_trip(pts)
        # float32 has ~7 decimal digits; for coords up to 500 mm
        # the error should be well under 0.01 mm
        assert np.all(errors < 0.01)

    def test_batch_matches_scalar(self, master: MasterCoordinateSpace) -> None:
        """Batch and scalar paths should produce identical results for float64."""
        pts = np.array([[100.0, 200.0], [0.5, 0.5], [420.0, 297.0]])
        batch_pipe = BatchPipeline(master, PRINTER_A3_300, dtype=np.float64)
        scalar_pipe = ScalarPipeline(master, PRINTER_A3_300)

        batch_result, _ = batch_pipe.forward(pts)

        for i in range(pts.shape[0]):
            scalar_result = scalar_pipe.forward(Point2D(pts[i, 0], pts[i, 1]))
            scalar_pt = scalar_result.final_output
            assert isinstance(scalar_pt, Point2D)
            assert abs(batch_result[i, 0] - scalar_pt.x) < 1e-6
            assert abs(batch_result[i, 1] - scalar_pt.y) < 1e-6

    def test_css_dpr_batch(self, master: MasterCoordinateSpace) -> None:
        pipe = BatchPipeline(master, IPAD_PRO_129)
        pts = np.array([[100.0, 200.0]])
        no_dpr, _ = pipe.forward(pts, apply_css_dpr=False)
        with_dpr, _ = pipe.forward(pts, apply_css_dpr=True)
        # DPR = 2 → CSS px = device px / 2
        np.testing.assert_allclose(with_dpr, no_dpr / 2.0, atol=1e-6)


# ---------------------------------------------------------------------------
# build_device_transform convenience
# ---------------------------------------------------------------------------

class TestBuildDeviceTransform:
    def test_printer_scale(self, master: MasterCoordinateSpace) -> None:
        tf = build_device_transform(master, PRINTER_A3_300)
        expected_scale = 300.0 / 25.4
        assert abs(tf.a - expected_scale) < 1e-10
        assert abs(tf.e - expected_scale) < 1e-10

    def test_ipad_with_dpr(self, master: MasterCoordinateSpace) -> None:
        tf = build_device_transform(master, IPAD_PRO_129, apply_css_dpr=True)
        expected_scale = 264.0 / 25.4 / 2.0  # ppi / 25.4 / dpr
        assert abs(tf.a - expected_scale) < 1e-10


# ---------------------------------------------------------------------------
# Device registry tests
# ---------------------------------------------------------------------------

class TestDeviceRegistry:
    def test_default_registry_has_three(self) -> None:
        reg = create_default_registry()
        assert len(reg) == 3

    def test_physical_dimensions_auto(self) -> None:
        # iPad: 2048 px / 264 ppi * 25.4 mm/in ≈ 197.0 mm
        assert abs(IPAD_PRO_129.physical_width_mm - 2048 / 264 * 25.4) < 0.1

    def test_printer_physical_dimensions(self) -> None:
        assert PRINTER_A3_300.physical_width_mm == 420.0
        assert PRINTER_A3_300.physical_height_mm == 297.0

    def test_pixels_per_mm(self) -> None:
        # 300 DPI → 300/25.4 ≈ 11.811 px/mm
        assert abs(PRINTER_A3_300.pixels_per_mm - 300 / 25.4) < 0.001

    def test_css_pixels_per_mm(self) -> None:
        # iPad 264 ppi / 25.4 / 2 (DPR) ≈ 5.197
        expected = 264.0 / 25.4 / 2.0
        assert abs(IPAD_PRO_129.css_pixels_per_mm - expected) < 0.001
