from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xarray as xr

from .storage import open_zarr_like


@dataclass(frozen=True)
class SurfaceProduct:
    """Adapter for surface regular-grid products."""

    path: Path
    vertical_support: str = "surface"

    def open(self) -> xr.Dataset:
        ds = open_zarr_like(self.path)
        ds.attrs.setdefault("product_type", "surface_regular_grid")
        ds.attrs.setdefault("vertical_support", self.vertical_support)
        return ds

    @staticmethod
    def matches_semantic_interval(z_top: float, z_bottom: float) -> bool:
        return bool(z_top <= 0.0 <= z_bottom)
