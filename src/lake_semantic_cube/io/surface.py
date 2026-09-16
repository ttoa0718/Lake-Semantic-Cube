from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import xarray as xr

from .storage import write_zarr_like


def build_surface_zarr_from_arrays(
    arrays: Mapping[str, np.ndarray],
    times: list | np.ndarray | pd.DatetimeIndex,
    y: list | np.ndarray,
    x: list | np.ndarray,
    output_path: str | Path,
    chunks: dict[str, int] | None = None,
    attrs: dict | None = None,
) -> xr.Dataset:
    """Create a surface regular-grid Zarr product with dimensions time, y, x."""
    coords = {"time": pd.DatetimeIndex(times), "y": np.asarray(y), "x": np.asarray(x)}
    expected_shape = (len(coords["time"]), len(coords["y"]), len(coords["x"]))
    data_vars = {}
    for name, values in arrays.items():
        arr = np.asarray(values)
        if arr.shape != expected_shape:
            raise ValueError(f"{name} has shape {arr.shape}, expected {expected_shape}")
        data_vars[name] = (("time", "y", "x"), arr.astype("float32"))
    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs.update(
        {
            "product_type": "surface_regular_grid",
            "vertical_support": "surface",
            "source_format": "array",
            "software_version": "0.1.0",
        }
    )
    if attrs:
        ds.attrs.update(attrs)
    encoding = {}
    if chunks:
        chunk_tuple = (
            int(chunks.get("time", len(coords["time"]))),
            int(chunks.get("y", len(coords["y"]))),
            int(chunks.get("x", len(coords["x"]))),
        )
        encoding = {name: {"chunks": chunk_tuple} for name in data_vars}
    write_zarr_like(ds, output_path, encoding=encoding)
    return ds
