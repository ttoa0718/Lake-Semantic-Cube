from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import xarray as xr

from .storage import write_zarr_like


def build_base_zarr_from_arrays(
    arrays: Mapping[str, np.ndarray],
    times: list | np.ndarray | pd.DatetimeIndex,
    layers: list | np.ndarray,
    y: list | np.ndarray,
    x: list | np.ndarray,
    output_path: str | Path,
    chunks: dict[str, int | str] | None = None,
    attrs: dict | None = None,
) -> xr.Dataset:
    """Create a base model Zarr product with dimensions time, layer, y, x."""
    coords = {
        "time": pd.DatetimeIndex(times),
        "layer": np.asarray(layers),
        "y": np.asarray(y),
        "x": np.asarray(x),
    }
    data_vars = {}
    expected_shape = (len(coords["time"]), len(coords["layer"]), len(coords["y"]), len(coords["x"]))
    for name, values in arrays.items():
        arr = np.asarray(values)
        if arr.shape != expected_shape:
            raise ValueError(f"{name} has shape {arr.shape}, expected {expected_shape}")
        data_vars[name] = (("time", "layer", "y", "x"), arr.astype("float32"))
    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs.update(
        {
            "product_type": "multi_layer_regular_grid",
            "source_format": "array",
            "layer_order": "surface_to_bottom",
            "vertical_reference_type": "configured",
            "software_version": "0.1.1",
        }
    )
    if attrs:
        ds.attrs.update(attrs)
    encoding = {}
    if chunks:
        chunk_tuple = (
            int(chunks.get("time", len(coords["time"]))),
            len(coords["layer"]) if chunks.get("layer") == "all" else int(chunks.get("layer", len(coords["layer"]))),
            int(chunks.get("y", len(coords["y"]))),
            int(chunks.get("x", len(coords["x"]))),
        )
        encoding = {name: {"chunks": chunk_tuple} for name in data_vars}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_zarr_like(ds, output_path, encoding=encoding)
    return ds


def partition_time(ds: xr.Dataset, output_dir: str | Path, hours_per_partition: int) -> list[Path]:
    """Write time-partitioned base Zarr products."""
    if hours_per_partition <= 0:
        raise ValueError("hours_per_partition must be positive")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for part, start in enumerate(range(0, ds.sizes["time"], hours_per_partition), start=1):
        subset = ds.isel(time=slice(start, start + hours_per_partition))
        path = output / f"model_part_{part:02d}.zarr"
        write_zarr_like(subset, path)
        paths.append(path)
    return paths
