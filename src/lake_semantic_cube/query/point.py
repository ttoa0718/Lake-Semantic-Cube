from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from lake_semantic_cube.io.storage import open_zarr_like

from .planner import QueryPlan


def _select_layer_range(array: xr.DataArray, start: int, end: int) -> xr.DataArray:
    if "layer" not in array.dims:
        return array
    layer_values = array["layer"].to_numpy() if "layer" in array.coords else np.array([])
    matches = np.where(np.isin(layer_values, [start, end]))[0]
    if matches.size == 2:
        lo = int(matches.min())
        hi = int(matches.max())
        return array.isel(layer=slice(lo, hi + 1))
    return array.isel(layer=slice(start, end + 1))


def query_point(plan: QueryPlan) -> pd.DataFrame:
    base = open_zarr_like(plan.base_datasets[-1].uri)
    semantic = open_zarr_like(plan.semantic_datasets[-1].uri)
    if "latitude" in base.dims:
        base = base.rename({"latitude": "y", "longitude": "x"})
    if "z" in base.dims:
        base = base.rename({"z": "layer"})
    y_index = plan.spatial_slice[0].start or 0
    x_index = plan.spatial_slice[1].start or 0
    semantic = semantic.sel(time=plan.time_slice).isel(y=y_index, x=x_index).load()
    base = base.sel(time=plan.time_slice).isel(y=y_index, x=x_index).load()
    rows = []
    for ti, time_value in enumerate(semantic.time.values):
        occurrence = int(semantic["occurrence"].isel(time=ti).item())
        start = int(semantic["layer_start"].isel(time=ti).item())
        end = int(semantic["layer_end"].isel(time=ti).item())
        for var in plan.query.variables:
            if occurrence and start >= 0 and var in base:
                values = _select_layer_range(base[var].isel(time=ti), start, end).to_numpy()
                value = float(np.nanmean(values)) if np.isfinite(values).any() else np.nan
            else:
                value = np.nan
            rows.append(
                {
                    "time": str(time_value),
                    "semantic_type": plan.semantic_type,
                    "occurrence": occurrence,
                    "z_top": float(semantic["z_top"].isel(time=ti).item()) if occurrence else np.nan,
                    "z_bottom": float(semantic["z_bottom"].isel(time=ti).item()) if occurrence else np.nan,
                    "thickness": float(semantic["thickness"].isel(time=ti).item()) if occurrence else np.nan,
                    "layer_start": start,
                    "layer_end": end,
                    "variable": var,
                    "value": value,
                }
            )
    return pd.DataFrame(rows)
