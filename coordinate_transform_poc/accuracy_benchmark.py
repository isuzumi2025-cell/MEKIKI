"""
Accuracy & Performance Benchmark

Measures:
* Round-trip accuracy (mm → px → mm) per device, per dtype.
* Per-stage timing breakdown.
* Throughput (points / second) for scalar vs. batch paths.
* Floating-point precision comparison: float64 vs float32 vs Python float.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from .device_registry import DeviceProfile, create_default_registry
from .master_schema import MasterCoordinateSpace, Point2D, Unit
from .transform_pipeline import BatchPipeline, ScalarPipeline


# ---------------------------------------------------------------------------
# Benchmark result types
# ---------------------------------------------------------------------------

@dataclass
class AccuracyReport:
    """Accuracy statistics for one device + dtype combination."""
    device_name: str
    dtype_name: str
    n_points: int
    max_abs_error_x: float
    max_abs_error_y: float
    mean_abs_error_x: float
    mean_abs_error_y: float
    median_abs_error_x: float
    median_abs_error_y: float
    p99_abs_error_x: float
    p99_abs_error_y: float
    max_rel_error: float          # max of |err| / |original| over all coords
    all_under_threshold: bool     # True if every error < threshold_mm
    threshold_mm: float

    def summary_line(self) -> str:
        return (
            f"{self.device_name:30s} | {self.dtype_name:8s} | "
            f"max_err=({self.max_abs_error_x:.2e}, {self.max_abs_error_y:.2e}) mm | "
            f"mean=({self.mean_abs_error_x:.2e}, {self.mean_abs_error_y:.2e}) | "
            f"p99=({self.p99_abs_error_x:.2e}, {self.p99_abs_error_y:.2e}) | "
            f"max_rel={self.max_rel_error:.2e} | "
            f"all<{self.threshold_mm}mm={'YES' if self.all_under_threshold else 'NO'}"
        )


@dataclass
class ThroughputReport:
    """Points-per-second measurement."""
    device_name: str
    path_name: str    # "scalar" or "batch_f64" or "batch_f32"
    n_points: int
    elapsed_s: float
    points_per_sec: float

    def summary_line(self) -> str:
        return (
            f"{self.device_name:30s} | {self.path_name:12s} | "
            f"n={self.n_points:>8d} | "
            f"elapsed={self.elapsed_s:.4f}s | "
            f"throughput={self.points_per_sec:,.0f} pts/s"
        )


@dataclass
class PrecisionComparison:
    """Compares the maximum error introduced by different dtypes."""
    device_name: str
    python_float_max_err: float
    numpy_f64_max_err: float
    numpy_f32_max_err: float
    f32_vs_f64_ratio: float  # how much worse f32 is

    def summary_line(self) -> str:
        return (
            f"{self.device_name:30s} | "
            f"py_float={self.python_float_max_err:.2e} | "
            f"np_f64={self.numpy_f64_max_err:.2e} | "
            f"np_f32={self.numpy_f32_max_err:.2e} | "
            f"f32/f64={self.f32_vs_f64_ratio:.1f}x"
        )


@dataclass
class FullBenchmarkReport:
    accuracy: List[AccuracyReport] = field(default_factory=list)
    throughput: List[ThroughputReport] = field(default_factory=list)
    precision: List[PrecisionComparison] = field(default_factory=list)

    def print_report(self) -> str:
        lines: List[str] = []
        lines.append("=" * 120)
        lines.append("MEKIKI Coordinate Transform POC — Benchmark Report")
        lines.append("=" * 120)

        lines.append("\n── Accuracy (round-trip mm → device px → mm) ──")
        for r in self.accuracy:
            lines.append(r.summary_line())

        lines.append("\n── Throughput ──")
        for r in self.throughput:
            lines.append(r.summary_line())

        lines.append("\n── Floating-Point Precision Comparison ──")
        for r in self.precision:
            lines.append(r.summary_line())

        lines.append("\n" + "=" * 120)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_master() -> MasterCoordinateSpace:
    return MasterCoordinateSpace(
        unit=Unit.MM,
        dpi=300.0,
        origin=Point2D(0.0, 0.0),
        page_width_mm=420.0,   # A3
        page_height_mm=297.0,
    )


def _generate_test_points(
    n: int,
    max_mm: float = 500.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return (n, 2) random points in [0, max_mm] mm."""
    if rng is None:
        rng = np.random.default_rng(42)
    return rng.uniform(0.0, max_mm, size=(n, 2))


# ---------------------------------------------------------------------------
# Accuracy measurement
# ---------------------------------------------------------------------------

def measure_accuracy(
    device: DeviceProfile,
    master: MasterCoordinateSpace | None = None,
    dtype: type = np.float64,
    n_points: int = 100_000,
    threshold_mm: float = 1e-6,
    apply_css_dpr: bool = False,
) -> AccuracyReport:
    """Measure round-trip accuracy for one device and dtype."""
    if master is None:
        master = _default_master()

    pipe = BatchPipeline(master, device, dtype=dtype)
    points = _generate_test_points(n_points)

    _, errors = pipe.round_trip(points, apply_css_dpr=apply_css_dpr)

    err_x = errors[:, 0]
    err_y = errors[:, 1]

    # Relative error (avoid division by zero)
    pts64 = points.astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(pts64 != 0, errors / np.abs(pts64), 0.0)
    max_rel = float(np.nanmax(rel))

    dtype_name = "float32" if dtype == np.float32 else "float64"

    return AccuracyReport(
        device_name=device.name,
        dtype_name=dtype_name,
        n_points=n_points,
        max_abs_error_x=float(np.max(err_x)),
        max_abs_error_y=float(np.max(err_y)),
        mean_abs_error_x=float(np.mean(err_x)),
        mean_abs_error_y=float(np.mean(err_y)),
        median_abs_error_x=float(np.median(err_x)),
        median_abs_error_y=float(np.median(err_y)),
        p99_abs_error_x=float(np.percentile(err_x, 99)),
        p99_abs_error_y=float(np.percentile(err_y, 99)),
        max_rel_error=max_rel,
        all_under_threshold=bool(np.all(errors < threshold_mm)),
        threshold_mm=threshold_mm,
    )


# ---------------------------------------------------------------------------
# Throughput measurement
# ---------------------------------------------------------------------------

def measure_throughput_scalar(
    device: DeviceProfile,
    master: MasterCoordinateSpace | None = None,
    n_points: int = 10_000,
) -> ThroughputReport:
    if master is None:
        master = _default_master()

    pipe = ScalarPipeline(master, device)
    rng = np.random.default_rng(42)
    pts = [(rng.uniform(0, 500), rng.uniform(0, 500)) for _ in range(n_points)]

    t0 = time.perf_counter()
    for x, y in pts:
        pipe.forward(Point2D(x, y))
    t1 = time.perf_counter()

    elapsed = t1 - t0
    return ThroughputReport(
        device_name=device.name,
        path_name="scalar",
        n_points=n_points,
        elapsed_s=elapsed,
        points_per_sec=n_points / elapsed if elapsed > 0 else 0,
    )


def measure_throughput_batch(
    device: DeviceProfile,
    master: MasterCoordinateSpace | None = None,
    n_points: int = 1_000_000,
    dtype: type = np.float64,
) -> ThroughputReport:
    if master is None:
        master = _default_master()

    pipe = BatchPipeline(master, device, dtype=dtype)
    pts = _generate_test_points(n_points)

    t0 = time.perf_counter()
    pipe.forward(pts)
    t1 = time.perf_counter()

    elapsed = t1 - t0
    dtype_name = "batch_f32" if dtype == np.float32 else "batch_f64"
    return ThroughputReport(
        device_name=device.name,
        path_name=dtype_name,
        n_points=n_points,
        elapsed_s=elapsed,
        points_per_sec=n_points / elapsed if elapsed > 0 else 0,
    )


# ---------------------------------------------------------------------------
# Precision comparison (Python float vs np.float64 vs np.float32)
# ---------------------------------------------------------------------------

def measure_precision_comparison(
    device: DeviceProfile,
    master: MasterCoordinateSpace | None = None,
    n_points: int = 100_000,
) -> PrecisionComparison:
    if master is None:
        master = _default_master()

    pts = _generate_test_points(n_points)

    # Python scalar round-trip
    spipe = ScalarPipeline(master, device)
    py_errors: List[float] = []
    for i in range(min(n_points, 10_000)):  # cap scalar at 10k
        pt = Point2D(float(pts[i, 0]), float(pts[i, 1]))
        fwd_result = spipe.forward(pt)
        fwd_pt = fwd_result.final_output
        assert isinstance(fwd_pt, Point2D)
        inv_result = spipe.inverse(fwd_pt)
        inv_pt = inv_result.final_output
        assert isinstance(inv_pt, Point2D)
        py_errors.append(max(abs(pt.x - inv_pt.x), abs(pt.y - inv_pt.y)))

    py_max = max(py_errors)

    # NumPy float64
    pipe64 = BatchPipeline(master, device, dtype=np.float64)
    _, err64 = pipe64.round_trip(pts)
    f64_max = float(np.max(err64))

    # NumPy float32
    pipe32 = BatchPipeline(master, device, dtype=np.float32)
    _, err32 = pipe32.round_trip(pts)
    f32_max = float(np.max(err32))

    ratio = f32_max / f64_max if f64_max > 0 else float("inf")

    return PrecisionComparison(
        device_name=device.name,
        python_float_max_err=py_max,
        numpy_f64_max_err=f64_max,
        numpy_f32_max_err=f32_max,
        f32_vs_f64_ratio=ratio,
    )


# ---------------------------------------------------------------------------
# Run full benchmark
# ---------------------------------------------------------------------------

def run_full_benchmark(
    n_accuracy: int = 100_000,
    n_throughput_scalar: int = 10_000,
    n_throughput_batch: int = 1_000_000,
) -> FullBenchmarkReport:
    """Execute the complete benchmark suite across all registered devices."""
    registry = create_default_registry()
    master = _default_master()
    report = FullBenchmarkReport()

    for name in registry.list_devices():
        device = registry.get(name)
        assert device is not None

        # Accuracy — float64 and float32
        for dt in [np.float64, np.float32]:
            report.accuracy.append(
                measure_accuracy(device, master, dtype=dt, n_points=n_accuracy)
            )

        # Throughput — scalar, batch_f64, batch_f32
        report.throughput.append(
            measure_throughput_scalar(device, master, n_points=n_throughput_scalar)
        )
        for dt in [np.float64, np.float32]:
            report.throughput.append(
                measure_throughput_batch(device, master, n_points=n_throughput_batch, dtype=dt)
            )

        # Precision comparison
        report.precision.append(
            measure_precision_comparison(device, master, n_points=n_accuracy)
        )

    return report


__all__ = [
    "AccuracyReport",
    "ThroughputReport",
    "PrecisionComparison",
    "FullBenchmarkReport",
    "measure_accuracy",
    "measure_throughput_scalar",
    "measure_throughput_batch",
    "measure_precision_comparison",
    "run_full_benchmark",
]
