from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from lake_semantic_cube.io.storage import open_zarr_like

from .planner import QueryPlan


def query_region(plan: QueryPlan, stats: tuple[str, ...] = ("mean", "min", "max", "sum", "count")) -> pd.DataFrame:
    base = open_zarr_like(plan.base_datasets[-1].uri)
    semantic = open_zarr_like(plan.semantic_datasets[-1].uri)
    if "latitude" in base.dims:
        base = base.rename({"latitude": "y", "longitude": "x"})
    if "z" in base.dims:
        base = base.rename({"z": "layer"})
    semantic = semantic.sel(time=plan.time_slice).isel(y=plan.spatial_slice[0], x=plan.spatial_slice[1])
    base = base.sel(time=plan.time_slice).isel(y=plan.spatial_slice[0], x=plan.spatial_slice[1])
    mask = semantic["semantic_mask"].transpose("time", "layer", "y", "x")
    rows = []
    for var in plan.query.variables:
        if var not in base:
            continue
        values = base[var].transpose("time", "layer", "y", "x").where(mask > 0).to_numpy()
        finite = values[np.isfinite(values)]
        row = {"semantic_type": plan.semantic_type, "variable": var}
        if "mean" in stats:
            row["mean"] = float(np.nanmean(finite)) if finite.size else np.nan
        if "min" in stats:
            row["min"] = float(np.nanmin(finite)) if finite.size else np.nan
        if "max" in stats:
            row["max"] = float(np.nanmax(finite)) if finite.size else np.nan
        if "sum" in stats:
            row["sum"] = float(np.nansum(finite)) if finite.size else 0.0
        if "count" in stats:
            row["count"] = int(finite.size)
        rows.append(row)
    return pd.DataFrame(rows)
