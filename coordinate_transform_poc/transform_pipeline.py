"""
Transform Pipeline — Master (mm) → Device (px)

Implements the full forward and inverse transformation between
the master print-space coordinate system and any registered device.

Pipeline stages
---------------
1. **Unit normalisation** — ensure input is in mm.
2. **mm → inches** — divide by 25.4.
3. **inches → device pixels** — multiply by device PPI.
4. **Orientation / offset adjustment** — apply device-specific origin shift.
5. **(Optional) CSS DPR scaling** — divide physical px by DPR for web devices.

Each stage is individually measurable so that accuracy and timing can be
captured per-stage.

Two code-paths are provided for every operation:
* **Scalar (pure-Python float64)** — one point at a time.
* **Batch (NumPy)** — vectorised over an (N, 2) array.

Floating-point variants
-----------------------
* ``float64`` (default) — IEEE 754 double precision.
* ``float32`` — IEEE 754 single precision, used to quantify precision loss.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .device_registry import DeviceProfile
from .master_schema import (
    MasterCoordinateSpace,
    Point2D,
    TransformMatrix,
    Unit,
    to_mm,
)


# ---------------------------------------------------------------------------
# Stage result container
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Captures the output and timing of one pipeline stage."""
    stage_name: str
    input_value: object
    output_value: object
    elapsed_ns: int = 0  # wall-clock nanoseconds

    @property
    def elapsed_us(self) -> float:
        return self.elapsed_ns / 1_000

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_ns / 1_000_000


@dataclass
class PipelineResult:
    """Full result of a master → device (or inverse) transformation."""
    device_name: str
    direction: str  # "forward" or "inverse"
    stages: List[StageResult] = field(default_factory=list)

    @property
    def total_elapsed_ns(self) -> int:
        return sum(s.elapsed_ns for s in self.stages)

    @property
    def total_elapsed_us(self) -> float:
        return self.total_elapsed_ns / 1_000

    @property
    def final_output(self) -> object:
        return self.stages[-1].output_value if self.stages else None


# ---------------------------------------------------------------------------
# Scalar (pure-Python) pipeline
# ---------------------------------------------------------------------------

class ScalarPipeline:
    """One-point-at-a-time transformation using Python floats."""

    def __init__(
        self,
        master: MasterCoordinateSpace,
        device: DeviceProfile,
    ) -> None:
        self.master = master
        self.device = device

    # -- forward: master mm → device px --------------------------------

    def forward(self, pt: Point2D, apply_css_dpr: bool = False) -> PipelineResult:
        """Transform a single master-space point to device pixels."""
        result = PipelineResult(device_name=self.device.name, direction="forward")

        # Stage 1: ensure mm
        t0 = time.perf_counter_ns()
        mm_x = to_mm(pt.x, self.master.unit)
        mm_y = to_mm(pt.y, self.master.unit)
        t1 = time.perf_counter_ns()
        mm_pt = Point2D(mm_x, mm_y)
        result.stages.append(StageResult("unit_to_mm", pt, mm_pt, t1 - t0))

        # Stage 2: mm → inches
        t0 = time.perf_counter_ns()
        in_x = mm_x / 25.4
        in_y = mm_y / 25.4
        t1 = time.perf_counter_ns()
        in_pt = Point2D(in_x, in_y)
        result.stages.append(StageResult("mm_to_inches", mm_pt, in_pt, t1 - t0))

        # Stage 3: inches → device pixels
        t0 = time.perf_counter_ns()
        px_x = in_x * self.device.ppi
        px_y = in_y * self.device.ppi
        t1 = time.perf_counter_ns()
        px_pt = Point2D(px_x, px_y)
        result.stages.append(StageResult("inches_to_device_px", in_pt, px_pt, t1 - t0))

        # Stage 4: orientation / offset (origin shift)
        t0 = time.perf_counter_ns()
        # For now the master origin is applied as a simple translation.
        origin_x = to_mm(self.master.origin.x, self.master.unit) / 25.4 * self.device.ppi
        origin_y = to_mm(self.master.origin.y, self.master.unit) / 25.4 * self.device.ppi
        adj_x = px_x - origin_x
        adj_y = px_y - origin_y
        t1 = time.perf_counter_ns()
        adj_pt = Point2D(adj_x, adj_y)
        result.stages.append(StageResult("origin_offset", px_pt, adj_pt, t1 - t0))

        # Stage 5 (optional): CSS DPR
        if apply_css_dpr and self.device.css_dpr != 1.0:
            t0 = time.perf_counter_ns()
            css_x = adj_x / self.device.css_dpr
            css_y = adj_y / self.device.css_dpr
            t1 = time.perf_counter_ns()
            css_pt = Point2D(css_x, css_y)
            result.stages.append(StageResult("css_dpr_scale", adj_pt, css_pt, t1 - t0))

        return result

    # -- inverse: device px → master mm --------------------------------

    def inverse(self, pt: Point2D, from_css: bool = False) -> PipelineResult:
        """Transform a device-pixel point back to master mm."""
        result = PipelineResult(device_name=self.device.name, direction="inverse")

        cur_x, cur_y = pt.x, pt.y

        # Stage 1 (optional): undo CSS DPR
        if from_css and self.device.css_dpr != 1.0:
            t0 = time.perf_counter_ns()
            cur_x *= self.device.css_dpr
            cur_y *= self.device.css_dpr
            t1 = time.perf_counter_ns()
            result.stages.append(
                StageResult("undo_css_dpr", pt, Point2D(cur_x, cur_y), t1 - t0)
            )

        # Stage 2: undo origin offset
        t0 = time.perf_counter_ns()
        origin_x = to_mm(self.master.origin.x, self.master.unit) / 25.4 * self.device.ppi
        origin_y = to_mm(self.master.origin.y, self.master.unit) / 25.4 * self.device.ppi
        cur_x += origin_x
        cur_y += origin_y
        t1 = time.perf_counter_ns()
        result.stages.append(
            StageResult("undo_origin_offset", pt, Point2D(cur_x, cur_y), t1 - t0)
        )

        # Stage 3: device pixels → inches
        t0 = time.perf_counter_ns()
        in_x = cur_x / self.device.ppi
        in_y = cur_y / self.device.ppi
        t1 = time.perf_counter_ns()
        result.stages.append(
            StageResult("device_px_to_inches", Point2D(cur_x, cur_y), Point2D(in_x, in_y), t1 - t0)
        )

        # Stage 4: inches → mm
        t0 = time.perf_counter_ns()
        mm_x = in_x * 25.4
        mm_y = in_y * 25.4
        t1 = time.perf_counter_ns()
        result.stages.append(
            StageResult("inches_to_mm", Point2D(in_x, in_y), Point2D(mm_x, mm_y), t1 - t0)
        )

        return result


# ---------------------------------------------------------------------------
# Batch (NumPy) pipeline
# ---------------------------------------------------------------------------

class BatchPipeline:
    """Vectorised transformation using NumPy arrays."""

    def __init__(
        self,
        master: MasterCoordinateSpace,
        device: DeviceProfile,
        dtype: type = np.float64,
    ) -> None:
        self.master = master
        self.device = device
        self.dtype = dtype

        # Pre-compute the combined forward affine matrix (mm → device px)
        self._build_matrices()

    def _build_matrices(self) -> None:
        """Pre-compute forward and inverse affine matrices."""
        ppi = self.device.ppi
        # mm → px  scale factor  =  ppi / 25.4
        s = ppi / 25.4

        # Origin offset in device pixels
        origin_x = to_mm(self.master.origin.x, self.master.unit) * s
        origin_y = to_mm(self.master.origin.y, self.master.unit) * s

        # Forward: scale then translate
        self.forward_matrix = np.array([
            [s,   0.0, -origin_x],
            [0.0, s,   -origin_y],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

        self.inverse_matrix = np.linalg.inv(self.forward_matrix)

        # CSS DPR variant
        if self.device.css_dpr != 1.0:
            dpr = self.device.css_dpr
            dpr_scale = np.diag([1.0 / dpr, 1.0 / dpr, 1.0])
            self.forward_matrix_css = dpr_scale @ self.forward_matrix
            self.inverse_matrix_css = np.linalg.inv(self.forward_matrix_css)
        else:
            self.forward_matrix_css = self.forward_matrix
            self.inverse_matrix_css = self.inverse_matrix

    def forward(
        self,
        points_mm: np.ndarray,
        apply_css_dpr: bool = False,
    ) -> Tuple[np.ndarray, PipelineResult]:
        """Transform (N, 2) mm → device pixels.

        Returns (transformed_points, pipeline_result).
        """
        result = PipelineResult(device_name=self.device.name, direction="forward_batch")
        pts = np.asarray(points_mm, dtype=self.dtype)
        n = pts.shape[0]

        # Homogeneous coordinates
        t0 = time.perf_counter_ns()
        ones = np.ones((n, 1), dtype=self.dtype)
        homo = np.hstack([pts, ones])  # (N, 3)
        t1 = time.perf_counter_ns()
        result.stages.append(StageResult("homogeneous_build", None, None, t1 - t0))

        # Matrix multiply
        mat = self.forward_matrix_css if apply_css_dpr else self.forward_matrix
        mat = mat.astype(self.dtype)

        t0 = time.perf_counter_ns()
        transformed = (mat @ homo.T).T[:, :2]  # (N, 2)
        t1 = time.perf_counter_ns()
        result.stages.append(StageResult("matmul_forward", None, None, t1 - t0))

        return transformed, result

    def inverse(
        self,
        points_px: np.ndarray,
        from_css: bool = False,
    ) -> Tuple[np.ndarray, PipelineResult]:
        """Transform (N, 2) device pixels → mm."""
        result = PipelineResult(device_name=self.device.name, direction="inverse_batch")
        pts = np.asarray(points_px, dtype=self.dtype)
        n = pts.shape[0]

        t0 = time.perf_counter_ns()
        ones = np.ones((n, 1), dtype=self.dtype)
        homo = np.hstack([pts, ones])
        t1 = time.perf_counter_ns()
        result.stages.append(StageResult("homogeneous_build", None, None, t1 - t0))

        mat = self.inverse_matrix_css if from_css else self.inverse_matrix
        mat = mat.astype(self.dtype)

        t0 = time.perf_counter_ns()
        transformed = (mat @ homo.T).T[:, :2]
        t1 = time.perf_counter_ns()
        result.stages.append(StageResult("matmul_inverse", None, None, t1 - t0))

        return transformed, result

    def round_trip(
        self,
        points_mm: np.ndarray,
        apply_css_dpr: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Forward then inverse; returns (recovered_mm, abs_error)."""
        fwd, _ = self.forward(points_mm, apply_css_dpr=apply_css_dpr)
        inv, _ = self.inverse(fwd, from_css=apply_css_dpr)
        error = np.abs(inv - np.asarray(points_mm, dtype=self.dtype))
        return inv, error


# ---------------------------------------------------------------------------
# Convenience: build a combined affine TransformMatrix for a device
# ---------------------------------------------------------------------------

def build_device_transform(
    master: MasterCoordinateSpace,
    device: DeviceProfile,
    apply_css_dpr: bool = False,
) -> TransformMatrix:
    """Return a single TransformMatrix that maps master mm → device px."""
    s = device.ppi / 25.4
    origin_x = to_mm(master.origin.x, master.unit) * s
    origin_y = to_mm(master.origin.y, master.unit) * s

    if apply_css_dpr and device.css_dpr != 1.0:
        s /= device.css_dpr
        origin_x /= device.css_dpr
        origin_y /= device.css_dpr

    return TransformMatrix(
        a=s, b=0.0, c=-origin_x,
        d=0.0, e=s, f=-origin_y,
    )


__all__ = [
    "StageResult",
    "PipelineResult",
    "ScalarPipeline",
    "BatchPipeline",
    "build_device_transform",
]
