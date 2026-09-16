from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from lake_semantic_cube.catalog.odc import ODCCatalog
from lake_semantic_cube.catalog.odc_core import BASE_ZARR_PRODUCT
from lake_semantic_cube.io.storage import open_zarr_like
from lake_semantic_cube.vertical.reference import VerticalReference

from .planner import _nearest
from .request import Point


def query_actual_depth(
    base_zarr: str,
    time_range: tuple[str, str],
    point: Point,
    actual_depth: float,
    variables: tuple[str, ...],
    vertical_reference: VerticalReference,
    water_depth: float,
) -> pd.DataFrame:
    """Query variables at an actual depth without requiring the user to know model layers."""
    base = open_zarr_like(base_zarr).sel(time=slice(time_range[0], time_range[1]))
    if "latitude" in base.dims:
        base = base.rename({"latitude": "y", "longitude": "x"})
    if "z" in base.dims:
        base = base.rename({"z": "layer"})
    layer_candidates = vertical_reference.depth_to_layers(actual_depth, actual_depth, water_depth)
    if not layer_candidates:
        layer_candidates = [
            min(
                range(vertical_reference.n_layers),
                key=lambda layer: abs(np.mean(vertical_reference.layer_to_depth(layer, water_depth)) - actual_depth),
            )
        ]
    layer = int(layer_candidates[0])
    layer_top, layer_bottom = vertical_reference.layer_to_depth(layer, water_depth)
    yi = _nearest(base["y"].to_numpy(), point.y)
    xi = _nearest(base["x"].to_numpy(), point.x)
    rows = []
    for ti, time_value in enumerate(base.time.values):
        for var in variables:
            value = np.nan
            if var in base:
                value = float(base[var].isel(time=ti, layer=layer, y=yi, x=xi).item())
            rows.append(
                {
                    "time": str(time_value),
                    "requested_depth": float(actual_depth),
                    "mapped_layer": layer,
                    "layer_z_top": float(layer_top),
                    "layer_z_bottom": float(layer_bottom),
                    "variable": var,
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


def query_actual_depth_with_catalog(
    catalog: ODCCatalog,
    time_range: tuple[str, str],
    point: Point,
    actual_depth: float,
    variables: tuple[str, ...],
    vertical_reference: VerticalReference,
    water_depth: float,
    product: str = BASE_ZARR_PRODUCT,
) -> pd.DataFrame:
    """Find the model Base Zarr through ODC/catalog metadata, then query by actual depth."""
    try:
        records = catalog.find_base_datasets(
            product=product,
            variables=list(variables),
            product_type="model",
            time=time_range,
            space=point,
        )
    except TypeError:
        records = catalog.find_base_datasets(product=product, variables=list(variables), product_type="model")
    if not records:
        raise LookupError(f"No base dataset found for actual-depth query: {product}")
    result = query_actual_depth(
        records[-1].uri,
        time_range,
        point,
        actual_depth,
        variables,
        vertical_reference,
        water_depth,
    )
    result["catalog_product"] = records[-1].product
    result["catalog_dataset"] = records[-1].id
    return result
