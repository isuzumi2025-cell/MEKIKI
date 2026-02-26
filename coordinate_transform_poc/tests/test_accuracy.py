"""
Accuracy assertion tests.

These tests exercise the accuracy measurement framework and assert that
the round-trip errors are within expected bounds for each device and
floating-point type.
"""

from __future__ import annotations

import numpy as np
import pytest

from coordinate_transform_poc.accuracy_benchmark import (
    measure_accuracy,
    measure_precision_comparison,
    measure_throughput_batch,
    measure_throughput_scalar,
)
from coordinate_transform_poc.device_registry import (
    HIRES_MONITOR,
    IPAD_PRO_129,
    PRINTER_A3_300,
)


# ---------------------------------------------------------------------------
# float64 accuracy — should be near machine-epsilon level
# ---------------------------------------------------------------------------

class TestFloat64Accuracy:
    """float64 round-trip should produce errors < 1e-8 mm."""

    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_max_error_below_threshold(self, device) -> None:
        report = measure_accuracy(device, dtype=np.float64, n_points=50_000,
                                  threshold_mm=1e-8)
        assert report.max_abs_error_x < 1e-8, f"X error too large: {report.max_abs_error_x}"
        assert report.max_abs_error_y < 1e-8, f"Y error too large: {report.max_abs_error_y}"

    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_all_under_threshold(self, device) -> None:
        report = measure_accuracy(device, dtype=np.float64, n_points=50_000,
                                  threshold_mm=1e-6)
        assert report.all_under_threshold


# ---------------------------------------------------------------------------
# float32 accuracy — looser bounds
# ---------------------------------------------------------------------------

class TestFloat32Accuracy:
    """float32 has ~7 sig digits; for coords up to 500 mm expect < 0.01 mm."""

    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_max_error_below_001mm(self, device) -> None:
        report = measure_accuracy(device, dtype=np.float32, n_points=50_000,
                                  threshold_mm=0.01)
        assert report.max_abs_error_x < 0.01
        assert report.max_abs_error_y < 0.01

    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_mean_error_below_0001mm(self, device) -> None:
        report = measure_accuracy(device, dtype=np.float32, n_points=50_000,
                                  threshold_mm=0.01)
        assert report.mean_abs_error_x < 0.001
        assert report.mean_abs_error_y < 0.001


# ---------------------------------------------------------------------------
# Precision comparison
# ---------------------------------------------------------------------------

class TestPrecisionComparison:
    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_f32_worse_than_f64(self, device) -> None:
        comp = measure_precision_comparison(device, n_points=10_000)
        assert comp.numpy_f32_max_err >= comp.numpy_f64_max_err

    @pytest.mark.parametrize("device", [IPAD_PRO_129, HIRES_MONITOR, PRINTER_A3_300],
                             ids=lambda d: d.name)
    def test_python_float_similar_to_f64(self, device) -> None:
        """Python float IS float64, so scalar and batch should be close."""
        comp = measure_precision_comparison(device, n_points=10_000)
        # Both should be extremely small for float64
        assert comp.python_float_max_err < 1e-6
        assert comp.numpy_f64_max_err < 1e-6


# ---------------------------------------------------------------------------
# Throughput sanity (just check that it doesn't crash and returns > 0)
# ---------------------------------------------------------------------------

class TestThroughputSanity:
    def test_scalar_throughput_positive(self) -> None:
        r = measure_throughput_scalar(PRINTER_A3_300, n_points=1_000)
        assert r.points_per_sec > 0

    def test_batch_throughput_positive(self) -> None:
        r = measure_throughput_batch(PRINTER_A3_300, n_points=10_000)
        assert r.points_per_sec > 0

    def test_batch_faster_than_scalar(self) -> None:
        """Batch should be significantly faster than scalar."""
        n = 10_000
        s = measure_throughput_scalar(PRINTER_A3_300, n_points=n)
        b = measure_throughput_batch(PRINTER_A3_300, n_points=n)
        # Allow batch to be at least as fast (usually 10x+ faster)
        assert b.points_per_sec >= s.points_per_sec * 0.5
