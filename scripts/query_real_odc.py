from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lake_semantic_cube.catalog.odc_core import OpenDataCubeDatasetCatalog
from lake_semantic_cube.io.efdc_tif import LAYER_DEPTH_MAP, SEMANTIC_DEFINITIONS
from lake_semantic_cube.io.storage import open_zarr_like
from lake_semantic_cube.query.planner import QueryPlanner
from lake_semantic_cube.query.point import query_point
from lake_semantic_cube.query.request import BBox, Point, QueryRequest


TIME_RANGE = ("2025-10-01 01:00:00", "2025-10-08 01:00:00")


def _normalize_base(ds):
    if "latitude" in ds.dims:
        ds = ds.rename({"latitude": "y", "longitude": "x"})
    if "z" in ds.dims:
        ds = ds.rename({"z": "layer"})
    return ds


def _clean(value):
    if isinstance(value, np.ndarray):
        return [_clean(item) for item in value.tolist()]
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


def _fig_to_data_url(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _build_request(args) -> QueryRequest:
    meta = SEMANTIC_DEFINITIONS[args.semantic]
    variable = args.variable or str(meta["variable"])
    if args.mode == "point":
        space = Point(float(args.x), float(args.y))
    else:
        space = BBox(float(args.min_x), float(args.min_y), float(args.max_x), float(args.max_y))
    return QueryRequest(time=TIME_RANGE, space=space, semantic=args.semantic, variables=(variable,), product_type="model")


def _plan(args):
    catalog = OpenDataCubeDatasetCatalog(cwd=args.root)
    request = _build_request(args)
    plan = QueryPlanner(catalog).plan(request)
    return request, plan


def query_point_payload(args) -> dict:
    request, plan = _plan(args)
    semantic = open_zarr_like(plan.semantic_datasets[-1].uri).sel(time=plan.time_slice)
    base = _normalize_base(open_zarr_like(plan.base_datasets[-1].uri)).sel(time=plan.time_slice)
    variable = request.variables[0]
    point_semantic = semantic.sel(x=request.space.x, y=request.space.y, method="nearest")
    point_base = base.sel(x=request.space.x, y=request.space.y, method="nearest")
    matrix = point_base[variable].transpose("layer", "time").to_numpy().astype("float64")
    query_rows = query_point(plan).replace({np.nan: None}).to_dict(orient="records")
    hours = list(range(1, int(point_semantic.sizes["time"]) + 1))
    boundary = {
        "hour": hours,
        "occurrence": point_semantic["occurrence"].to_numpy().astype("int8").tolist(),
        "z_top": _clean(point_semantic["z_top"].to_numpy().astype("float64")),
        "z_bottom": _clean(point_semantic["z_bottom"].to_numpy().astype("float64")),
        "thickness": _clean(point_semantic["thickness"].to_numpy().astype("float64")),
        "layer_start": point_semantic["layer_start"].to_numpy().astype("int16").tolist(),
        "layer_end": point_semantic["layer_end"].to_numpy().astype("int16").tolist(),
    }
    return {
        "catalog_mode": "Open Data Cube",
        "logs": [
            "ODC dataset discovery: semantic product changtan_vertical_semantic_real",
            "ODC dataset discovery: base product changtan_base_zarr_real",
            "Array access: xarray opens Semantic Zarr and Base Zarr from ODC dataset locations",
        ],
        "semantic_dataset": plan.semantic_datasets[-1].id,
        "semantic_source": plan.semantic_datasets[-1].uri,
        "base_dataset": plan.base_datasets[-1].id,
        "base_source": plan.base_datasets[-1].uri,
        "hours": hours,
        "depth": [float(LAYER_DEPTH_MAP[int(layer)]) for layer in point_base["layer"].to_numpy()],
        "matrix": _clean(matrix),
        "boundary": boundary,
        "query_rows": query_rows,
        "rule": f"{SEMANTIC_DEFINITIONS[args.semantic]['variable']} {SEMANTIC_DEFINITIONS[args.semantic]['operator']} {SEMANTIC_DEFINITIONS[args.semantic]['threshold']}",
    }


def query_region_payload(args) -> dict:
    request, plan = _plan(args)
    semantic = open_zarr_like(plan.semantic_datasets[-1].uri).sel(time=plan.time_slice).isel(
        y=plan.spatial_slice[0],
        x=plan.spatial_slice[1],
    )
    thickness = semantic["thickness"]
    if thickness.sizes["time"] > 28:
        indices = np.linspace(0, thickness.sizes["time"] - 1, 28).round().astype("int64")
    else:
        indices = np.arange(thickness.sizes["time"])
    panels = []
    for t_index in indices:
        t_index = int(t_index)
        arr = thickness.isel(time=t_index).to_numpy().astype("float64")
        arr = _downsample(arr, max_size=160)
        panels.append({"hour": t_index + 1, "thickness": _clean(arr)})
    finite = thickness.to_numpy().astype("float64")
    finite = finite[np.isfinite(finite)]
    stats = [
        {
            "semantic_type": args.semantic,
            "variable": "thickness",
            "mean": float(np.nanmean(finite)) if finite.size else None,
            "min": float(np.nanmin(finite)) if finite.size else None,
            "max": float(np.nanmax(finite)) if finite.size else None,
            "count": int(finite.size),
        }
    ]
    return {
        "catalog_mode": "Open Data Cube",
        "logs": [
            "ODC dataset discovery: semantic product changtan_vertical_semantic_real",
            "ODC dataset discovery: base product changtan_base_zarr_real",
            "Regional visualization reads thickness directly from Semantic Zarr",
        ],
        "semantic_dataset": plan.semantic_datasets[-1].id,
        "semantic_source": plan.semantic_datasets[-1].uri,
        "base_dataset": plan.base_datasets[-1].id,
        "base_source": plan.base_datasets[-1].uri,
        "panels": panels,
        "stats": stats,
        "time_steps": int(thickness.sizes["time"]),
    }


def _downsample(arr: np.ndarray, max_size: int) -> np.ndarray:
    step_y = max(1, int(np.ceil(arr.shape[0] / max_size)))
    step_x = max(1, int(np.ceil(arr.shape[1] / max_size)))
    return arr[::step_y, ::step_x]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real ODC-backed semantic queries for the local UI.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=["point", "region"], required=True)
    parser.add_argument("--semantic", required=True, choices=sorted(SEMANTIC_DEFINITIONS))
    parser.add_argument("--variable", default=None)
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    parser.add_argument("--min-x", type=float)
    parser.add_argument("--min-y", type=float)
    parser.add_argument("--max-x", type=float)
    parser.add_argument("--max-y", type=float)
    args = parser.parse_args()
    args.root = Path(args.root).resolve()
    payload = query_point_payload(args) if args.mode == "point" else query_region_payload(args)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
