from __future__ import annotations

from pathlib import Path

import xarray as xr

from lake_semantic_cube.io.storage import write_zarr_like

from .metadata import semantic_attrs


def write_semantic_zarr(ds: xr.Dataset, output_path: str | Path) -> None:
    """Write a Semantic Zarr product without duplicating base variables."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        "occurrence": {"_FillValue": 0},
        "segment_count": {"_FillValue": 0},
        "layer_start": {"_FillValue": -1},
        "layer_end": {"_FillValue": -1},
    }
    write_zarr_like(ds, output_path, encoding=encoding)


__all__ = ["semantic_attrs", "write_semantic_zarr"]
