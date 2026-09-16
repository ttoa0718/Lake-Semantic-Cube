from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import tifffile

from lake_semantic_cube.catalog.eo3 import deterministic_dataset_uuid
from lake_semantic_cube.catalog.odc import DatasetRecord, ODCCatalog
from lake_semantic_cube.catalog.odc_core import BASE_ZARR_PRODUCT
from lake_semantic_cube.io.efdc_tif import LAYER_DEPTH_MAP, SEMANTIC_DEFINITIONS, raster_grid, scan_efdc_tifs


RULES = {key: value for key, value in SEMANTIC_DEFINITIONS.items() if value.get("idx") is not None}


def _compare(values: np.ndarray, operator: str, threshold: float) -> np.ndarray:
    if operator == "<":
        return values < threshold
    if operator == ">":
        return values > threshold
    if operator == "<=":
        return values <= threshold
    if operator == ">=":
        return values >= threshold
    raise ValueError(f"Unsupported operator: {operator}")


def build_semantic_from_hourtif(
    tif_dir: Path,
    output_zarr: Path,
    catalog_path: Path,
    semantic_type: str,
    start_hour: int,
    end_hour: int,
) -> dict:
    rule = RULES[semantic_type]
    idx = int(rule["idx"])
    records = [item for item in scan_efdc_tifs(tif_dir) if item.idx == idx and start_hour <= item.hour <= end_hour]
    if not records:
        raise RuntimeError(f"No TIF records found for idx={idx} in {tif_dir}")
    grid = raster_grid(records[0].path)
    layers = sorted(LAYER_DEPTH_MAP)
    depths = np.array([LAYER_DEPTH_MAP[layer] for layer in layers], dtype="float32")
    hours = sorted({item.hour for item in records})
    by_hour_layer = {(item.hour, item.layer): item.path for item in records}

    shape3 = (len(hours), grid.height, grid.width)
    shape4 = (len(hours), len(layers), grid.height, grid.width)
    occurrence = np.zeros(shape3, dtype="uint8")
    z_top = np.full(shape3, np.nan, dtype="float32")
    z_bottom = np.full(shape3, np.nan, dtype="float32")
    thickness = np.full(shape3, np.nan, dtype="float32")
    core_depth = np.full(shape3, np.nan, dtype="float32")
    segment_count = np.zeros(shape3, dtype="int16")
    layer_start = np.full(shape3, -1, dtype="int16")
    layer_end = np.full(shape3, -1, dtype="int16")
    semantic_mask = np.zeros(shape4, dtype="uint8")

    for t_index, hour in enumerate(hours):
        stack = []
        for layer in layers:
            path = by_hour_layer.get((hour, layer))
            if path is None:
                stack.append(np.full((grid.height, grid.width), np.nan, dtype="float32"))
                continue
            arr = tifffile.imread(str(path)).astype("float32")
            arr[arr == -999.0] = np.nan
            stack.append(arr)
        values = np.stack(stack, axis=0)
        mask = np.nan_to_num(_compare(values, str(rule["operator"]), float(rule["threshold"])), nan=False)
        semantic_mask[t_index] = mask.astype("uint8")
        has_object = mask.any(axis=0)
        occurrence[t_index, has_object] = 1
        segment_count[t_index, has_object] = 1
        first = np.argmax(mask, axis=0)
        last = len(layers) - 1 - np.argmax(mask[::-1], axis=0)
        top_depth = np.minimum(depths[first], depths[last])
        bottom_depth = np.maximum(depths[first], depths[last])
        z_top[t_index, has_object] = top_depth[has_object]
        z_bottom[t_index, has_object] = bottom_depth[has_object]
        thickness[t_index, has_object] = (bottom_depth - top_depth)[has_object]
        core_depth[t_index, has_object] = ((bottom_depth + top_depth) / 2.0)[has_object]
        layer_start[t_index, has_object] = np.array(layers, dtype="int16")[first][has_object]
        layer_end[t_index, has_object] = np.array(layers, dtype="int16")[last][has_object]
        print(f"hour {hour}: occurrence pixels={int(has_object.sum())}")

    times = pd.date_range("2025-10-01 01:00:00", periods=len(hours), freq="h")
    y = np.linspace(grid.max_y, grid.min_y, grid.height, dtype="float64")
    x = np.linspace(grid.min_x, grid.max_x, grid.width, dtype="float64")
    ds = xr.Dataset(
        {
            "occurrence": (("time", "y", "x"), occurrence),
            "z_top": (("time", "y", "x"), z_top),
            "z_bottom": (("time", "y", "x"), z_bottom),
            "thickness": (("time", "y", "x"), thickness),
            "core_depth": (("time", "y", "x"), core_depth),
            "segment_count": (("time", "y", "x"), segment_count),
            "layer_start": (("time", "y", "x"), layer_start),
            "layer_end": (("time", "y", "x"), layer_end),
            "semantic_mask": (("time", "layer", "y", "x"), semantic_mask),
        },
        coords={"time": times, "layer": layers, "y": y, "x": x},
        attrs={
            "semantic_type": semantic_type,
            "rule_id": semantic_type,
            "rule_version": "real-hourtif-v1",
            "source_product": BASE_ZARR_PRODUCT,
            "source_variables": json.dumps([rule["variable"]]),
            "vertical_reference": json.dumps({"layer_depth_m": LAYER_DEPTH_MAP, "layer_order": "bottom_to_surface"}),
            "threshold": float(rule["threshold"]),
            "operator": str(rule["operator"]),
            "upper_label": str(rule.get("upper_label", "")),
            "lower_label": str(rule.get("lower_label", "")),
            "primary_segment_policy": "first_last_true_layer_for_real_hourtif",
            "index_role": "vertical_semantic_index",
        },
    )
    output_zarr.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        "occurrence": {"chunks": (24, 64, 64)},
        "z_top": {"chunks": (24, 64, 64)},
        "z_bottom": {"chunks": (24, 64, 64)},
        "thickness": {"chunks": (24, 64, 64)},
        "core_depth": {"chunks": (24, 64, 64)},
        "segment_count": {"chunks": (24, 64, 64)},
        "layer_start": {"chunks": (24, 64, 64)},
        "layer_end": {"chunks": (24, 64, 64)},
        "semantic_mask": {"chunks": (24, len(layers), 64, 64)},
    }
    ds.to_zarr(output_zarr, mode="w", consolidated=True, encoding=encoding)

    catalog = ODCCatalog(catalog_path)
    source_variables = sorted({str(item["variable"]) for item in RULES.values()})
    base_id = deterministic_dataset_uuid("changtan_efdc_hourtif_real", tif_dir.resolve(), str(times[0]), str(times[-1]))
    semantic_id = deterministic_dataset_uuid("changtan_vertical_semantic_real", output_zarr, str(times[0]), str(times[-1]), semantic_type, "real-hourtif-v1")
    catalog.register_product("changtan_efdc_hourtif_real", {"name": "changtan_efdc_hourtif_real", "format": "GeoTIFF collection"})
    catalog.register_product("changtan_vertical_semantic_real", {"name": "changtan_vertical_semantic_real", "format": "Zarr"})
    catalog.register_datasets(
        [
            DatasetRecord(
                id=base_id,
                product="changtan_efdc_hourtif_real",
                uri=str(tif_dir.resolve()),
                data_type="model_tif_collection",
                variables=source_variables,
                time_start=str(times[0]),
                time_end=str(times[-1]),
            ),
            DatasetRecord(
                id=semantic_id,
                product="changtan_vertical_semantic_real",
                uri=str(output_zarr),
                data_type="semantic",
                variables=list(ds.data_vars),
                properties={
                    "semantic:type": semantic_type,
                    "semantic:rule_id": semantic_type,
                    "semantic:rule_version": "real-hourtif-v1",
                    "semantic:source_product": BASE_ZARR_PRODUCT,
                    "semantic:operator": str(rule["operator"]),
                    "semantic:threshold": float(rule["threshold"]),
                    "semantic:upper_label": str(rule.get("upper_label", "")),
                    "semantic:lower_label": str(rule.get("lower_label", "")),
                    "odc:file_format": "Zarr",
                },
                time_start=str(times[0]),
                time_end=str(times[-1]),
            ),
        ]
    )
    return {"semantic_zarr": str(output_zarr), "catalog": str(catalog_path), "hours": len(hours)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tif-dir", required=True)
    parser.add_argument("--output-zarr", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--semantic", default="hypoxia_layer", choices=sorted(RULES))
    parser.add_argument("--start-hour", type=int, default=1)
    parser.add_argument("--end-hour", type=int, default=169)
    args = parser.parse_args()
    result = build_semantic_from_hourtif(
        tif_dir=Path(args.tif_dir),
        output_zarr=Path(args.output_zarr),
        catalog_path=Path(args.catalog),
        semantic_type=args.semantic,
        start_hour=args.start_hour,
        end_hour=args.end_hour,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
