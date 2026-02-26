"""
Device Registry

Maintains a catalogue of target output devices, each described by its
physical dimensions, pixel resolution, PPI/DPI, orientation, and any
device-specific quirks (CSS device-pixel-ratio for web, colour profile,
etc.).

Three representative devices are pre-registered:
  1. iPad Pro 12.9" (2048 x 2732 @ 264 PPI, CSS DPR 2)
  2. High-resolution monitor (3840 x 2160 @ 163 PPI, landscape)
  3. Printer — A3 sheet at 300 DPI (4960 x 3508 px)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from .master_schema import TransformMatrix


class Orientation(Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True)
class DeviceProfile:
    """Immutable description of an output device."""
    name: str
    width_px: int
    height_px: int
    ppi: float                        # physical pixels per inch
    orientation: Orientation
    css_dpr: float = 1.0              # CSS device-pixel-ratio (web only)
    physical_width_mm: float = 0.0    # viewable area width  (mm)
    physical_height_mm: float = 0.0   # viewable area height (mm)
    colour_profile: str = "sRGB"
    description: str = ""

    def __post_init__(self) -> None:
        # Auto-compute physical dimensions from pixel size and PPI
        # if the caller didn't supply them.
        if self.physical_width_mm == 0.0 and self.ppi > 0:
            object.__setattr__(
                self, "physical_width_mm",
                self.width_px / self.ppi * 25.4,
            )
        if self.physical_height_mm == 0.0 and self.ppi > 0:
            object.__setattr__(
                self, "physical_height_mm",
                self.height_px / self.ppi * 25.4,
            )

    @property
    def mm_per_pixel(self) -> float:
        """How many mm one device pixel spans."""
        return 25.4 / self.ppi if self.ppi > 0 else 0.0

    @property
    def pixels_per_mm(self) -> float:
        """How many device pixels span one mm."""
        return self.ppi / 25.4 if self.ppi > 0 else 0.0

    @property
    def css_pixels_per_mm(self) -> float:
        """For web devices: CSS px per mm (factoring out DPR)."""
        return self.pixels_per_mm / self.css_dpr


# ---------------------------------------------------------------------------
# Pre-registered representative devices
# ---------------------------------------------------------------------------

IPAD_PRO_129 = DeviceProfile(
    name="iPad Pro 12.9″",
    width_px=2048,
    height_px=2732,
    ppi=264.0,
    orientation=Orientation.PORTRAIT,
    css_dpr=2.0,
    colour_profile="Display P3",
    description="iPad Pro 12.9-inch (5th gen), Liquid Retina XDR",
)

HIRES_MONITOR = DeviceProfile(
    name="Hi-Res Monitor 4K",
    width_px=3840,
    height_px=2160,
    ppi=163.0,
    orientation=Orientation.LANDSCAPE,
    css_dpr=1.5,
    colour_profile="sRGB",
    description="32″ 4K UHD monitor, typical proofing display",
)

PRINTER_A3_300 = DeviceProfile(
    name="Printer A3 @300 DPI",
    width_px=4960,   # 420 mm / 25.4 * 300 ≈ 4961 (rounded)
    height_px=3508,  # 297 mm / 25.4 * 300 ≈ 3508
    ppi=300.0,
    orientation=Orientation.LANDSCAPE,
    physical_width_mm=420.0,   # A3 long edge
    physical_height_mm=297.0,  # A3 short edge
    colour_profile="FOGRA39",
    description="A3 sheet printed at 300 DPI (offset / inkjet proof)",
)


# ---------------------------------------------------------------------------
# Registry singleton
# ---------------------------------------------------------------------------

class DeviceRegistry:
    """Simple in-memory registry of DeviceProfiles."""

    def __init__(self) -> None:
        self._devices: Dict[str, DeviceProfile] = {}

    def register(self, profile: DeviceProfile) -> None:
        self._devices[profile.name] = profile

    def get(self, name: str) -> Optional[DeviceProfile]:
        return self._devices.get(name)

    def list_devices(self) -> list[str]:
        return list(self._devices.keys())

    def __len__(self) -> int:
        return len(self._devices)


def create_default_registry() -> DeviceRegistry:
    """Return a registry pre-loaded with the three representative devices."""
    reg = DeviceRegistry()
    reg.register(IPAD_PRO_129)
    reg.register(HIRES_MONITOR)
    reg.register(PRINTER_A3_300)
    return reg


__all__ = [
    "Orientation",
    "DeviceProfile",
    "IPAD_PRO_129",
    "HIRES_MONITOR",
    "PRINTER_A3_300",
    "DeviceRegistry",
    "create_default_registry",
]
