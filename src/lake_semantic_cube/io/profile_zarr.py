from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr

from .storage import open_zarr_like


@dataclass(frozen=True)
class ProfileProduct:
    """Adapter for point vertical profile products already stored as Zarr.

    Prefer `ProfileAdapter` in `io/profile.py` for raw CSV/XLS/XLSX observations.
    """

    path: Path

    def open(self) -> xr.Dataset:
        ds = open_zarr_like(self.path)
        ds.attrs.setdefault("product_type", "point_vertical_profile")
        return ds

    @staticmethod
    def depth_mask(depths: np.ndarray, z_top: float, z_bottom: float) -> np.ndarray:
        return (depths >= z_top) & (depths <= z_bottom)
