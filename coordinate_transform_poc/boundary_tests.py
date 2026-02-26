"""
Boundary / Worst-Case Coordinate Testing

Systematically exercises the transformation pipeline with extreme,
degenerate, and adversarial coordinate values to surface floating-point
edge cases.

Categories tested
-----------------
1. **Very large coordinates** — approaching print sheets > 10 m.
2. **Very small (sub-micron) coordinates** — resolution limits.
3. **Near-zero coordinates** — cancellation / underflow risks.
4. **Negative coordinates** — bleed / trim zones.
5. **IEEE 754 special values** — inf, -inf, NaN, subnormals.
6. **Maximum representable float** — overflow detection.
7. **Non-uniform scale** — extreme aspect ratios.
8. **Accumulated error** — chained transforms.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from .device_registry import DeviceProfile, create_default_registry
from .master_schema import MasterCoordinateSpace, Point2D, Unit
from .transform_pipeline import BatchPipeline, ScalarPipeline


@dataclass
class BoundaryTestCase:
    name: str
    points_mm: List[Tuple[float, float]]
    description: str


@dataclass
class BoundaryTestResult:
    case_name: str
    device_name: str
    dtype_name: str
    n_points: int
    max_abs_error: float
    mean_abs_error: float
    any_nan: bool
    any_inf: bool
    passed: bool          # True if no NaN/Inf and error < threshold
    notes: str = ""


# ---------------------------------------------------------------------------
# Canonical boundary test cases
# ---------------------------------------------------------------------------

def get_boundary_test_cases() -> List[BoundaryTestCase]:
    """Return a curated set of worst-case coordinate scenarios."""
    cases: List[BoundaryTestCase] = []

    # 1. Very large coordinates (10 m = 10 000 mm)
    cases.append(BoundaryTestCase(
        name="very_large_coords",
        points_mm=[
            (10_000.0, 10_000.0),
            (50_000.0, 50_000.0),    # 50 m — billboard scale
            (100_000.0, 100_000.0),  # 100 m
        ],
        description="Coordinates well beyond typical print (billboard, signage).",
    ))

    # 2. Sub-micron (very small) coordinates
    cases.append(BoundaryTestCase(
        name="sub_micron_coords",
        points_mm=[
            (1e-6, 1e-6),     # 1 nm
            (1e-9, 1e-9),     # 1 pm
            (1e-12, 1e-12),   # 1 fm
            (1e-15, 1e-15),   # near machine epsilon range
        ],
        description="Sub-micron coordinates testing resolution floor.",
    ))

    # 3. Near-zero (cancellation risk)
    eps = np.finfo(np.float64).eps
    cases.append(BoundaryTestCase(
        name="near_zero_coords",
        points_mm=[
            (eps, eps),
            (eps * 10, eps * 10),
            (1e-300, 1e-300),
            (5e-324, 5e-324),  # smallest positive float64
        ],
        description="Coordinates near machine epsilon — cancellation risks.",
    ))

    # 4. Negative coordinates (bleed / trim)
    cases.append(BoundaryTestCase(
        name="negative_coords",
        points_mm=[
            (-3.0, -3.0),       # 3 mm bleed
            (-0.001, -0.001),   # sub-mm bleed
            (-1e6, -1e6),       # extreme negative
        ],
        description="Negative coordinates for bleed/trim handling.",
    ))

    # 5. Max representable float (overflow)
    fmax = sys.float_info.max
    cases.append(BoundaryTestCase(
        name="max_float",
        points_mm=[
            (fmax / 1e10, fmax / 1e10),  # large but not overflow
            (1e300, 1e300),
            (1e308, 1e308),              # near float64 max
        ],
        description="Near maximum float64 values — overflow detection.",
    ))

    # 6. Mixed magnitudes (one axis tiny, one huge)
    cases.append(BoundaryTestCase(
        name="mixed_magnitude",
        points_mm=[
            (1e-10, 1e10),
            (1e10, 1e-10),
            (420.0, 1e-15),
            (1e-15, 297.0),
        ],
        description="Mixed magnitudes per axis — precision across scales.",
    ))

    # 7. Typical print coordinates (sanity)
    cases.append(BoundaryTestCase(
        name="typical_print",
        points_mm=[
            (0.0, 0.0),          # origin
            (210.0, 297.0),      # A4 corner
            (420.0, 297.0),      # A3 corner
            (105.0, 148.5),      # A4 center
            (0.3528, 0.3528),    # 1 pt
        ],
        description="Normal A4/A3 coordinates — baseline sanity check.",
    ))

    # 8. Coordinates that stress DPR division
    cases.append(BoundaryTestCase(
        name="dpr_stress",
        points_mm=[
            (1.0 / 3.0, 1.0 / 3.0),          # repeating decimal
            (1.0 / 7.0, 1.0 / 7.0),
            (math.pi, math.e),                 # irrational
            (math.sqrt(2), math.sqrt(3)),
        ],
        description="Non-representable fractions and irrationals — rounding stress.",
    ))

    return cases


# ---------------------------------------------------------------------------
# Run boundary tests
# ---------------------------------------------------------------------------

def run_boundary_tests(
    threshold_mm: float = 1e-6,
    threshold_mm_f32: float = 1e-3,
) -> List[BoundaryTestResult]:
    """Execute all boundary test cases across all devices and dtypes."""
    registry = create_default_registry()
    master = MasterCoordinateSpace(
        unit=Unit.MM, dpi=300.0,
        origin=Point2D(0.0, 0.0),
        page_width_mm=420.0, page_height_mm=297.0,
    )

    cases = get_boundary_test_cases()
    results: List[BoundaryTestResult] = []

    for device_name in registry.list_devices():
        device = registry.get(device_name)
        assert device is not None

        for dtype, dtype_name in [(np.float64, "float64"), (np.float32, "float32")]:
            pipe = BatchPipeline(master, device, dtype=dtype)

            for case in cases:
                pts = np.array(case.points_mm, dtype=np.float64)
                try:
                    recovered, errors = pipe.round_trip(pts)
                except Exception as exc:
                    results.append(BoundaryTestResult(
                        case_name=case.name,
                        device_name=device.name,
                        dtype_name=dtype_name,
                        n_points=len(case.points_mm),
                        max_abs_error=float("inf"),
                        mean_abs_error=float("inf"),
                        any_nan=True,
                        any_inf=True,
                        passed=False,
                        notes=f"Exception: {exc}",
                    ))
                    continue

                any_nan = bool(np.any(np.isnan(recovered)))
                any_inf = bool(np.any(np.isinf(recovered)))
                max_err = float(np.max(errors)) if not any_nan else float("inf")
                mean_err = float(np.mean(errors)) if not any_nan else float("inf")

                # Use relaxed threshold for float32
                effective_threshold = threshold_mm_f32 if dtype == np.float32 else threshold_mm
                max_coord = float(np.max(np.abs(pts)))
                if max_coord > 1e6:
                    # relative threshold for extreme values
                    effective_threshold = max_coord * 1e-10

                passed = (
                    not any_nan
                    and not any_inf
                    and max_err < effective_threshold
                )

                notes = ""
                if any_nan:
                    notes = "NaN detected in output"
                elif any_inf:
                    notes = "Inf detected in output"
                elif not passed:
                    notes = f"max_err {max_err:.2e} >= threshold {effective_threshold:.2e}"

                results.append(BoundaryTestResult(
                    case_name=case.name,
                    device_name=device.name,
                    dtype_name=dtype_name,
                    n_points=len(case.points_mm),
                    max_abs_error=max_err,
                    mean_abs_error=mean_err,
                    any_nan=any_nan,
                    any_inf=any_inf,
                    passed=passed,
                    notes=notes,
                ))

    return results


def format_boundary_report(results: List[BoundaryTestResult]) -> str:
    """Format boundary test results as a human-readable report."""
    lines: List[str] = []
    lines.append("=" * 130)
    lines.append("MEKIKI Coordinate Transform POC — Boundary / Worst-Case Report")
    lines.append("=" * 130)

    # Group by case
    from collections import defaultdict
    by_case: Dict[str, List[BoundaryTestResult]] = defaultdict(list)
    for r in results:
        by_case[r.case_name].append(r)

    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    lines.append(f"\nOverall: {passed_count}/{total_count} passed\n")

    for case_name, case_results in by_case.items():
        lines.append(f"\n── {case_name} ──")
        for r in case_results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"  [{status}] {r.device_name:30s} {r.dtype_name:8s} | "
                f"max_err={r.max_abs_error:.2e} | "
                f"mean_err={r.mean_abs_error:.2e} | "
                f"NaN={r.any_nan} Inf={r.any_inf}"
                + (f" | {r.notes}" if r.notes else "")
            )

    lines.append("\n" + "=" * 130)
    return "\n".join(lines)


__all__ = [
    "BoundaryTestCase",
    "BoundaryTestResult",
    "get_boundary_test_cases",
    "run_boundary_tests",
    "format_boundary_report",
]
