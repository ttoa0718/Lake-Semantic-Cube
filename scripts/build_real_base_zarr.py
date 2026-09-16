from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import xarray as xr

from lake_semantic_cube.catalog.eo3 import deterministic_dataset_uuid
from lake_semantic_cube.catalog.odc import DatasetRecord, ODCCatalog
from lake_semantic_cube.io.efdc_tif import LAYER_DEPTH_MAP, SEMANTIC_DEFINITIONS, default_efdc_root, raster_grid, scan_efdc_tifs


def build_real_base_zarr(tif_dir: Path, output_zarr: Path, start_hour: int = 1, end_hour: int = 169) -> dict:
    definitions = {key: value for key, value in SEMANTIC_DEFINITIONS.items() if value.get("idx") is not None}
    records = scan_efdc_tifs(tif_dir)
    if not records:
        raise RuntimeError(f"No EFDC TIF records found in {tif_dir}")
    grid = raster_grid(records[0].path)
    layers = sorted(LAYER_DEPTH_MAP)
    hours = sorted({item.hour for item in records if start_hour <= item.hour <= end_hour})
    if not hours:
        raise RuntimeError(f"No EFDC TIF records found for hours {start_hour}-{end_hour}")

    coords = {
        "time": pd.date_range("2025-10-01 01:00:00", periods=len(hours), freq="h"),
        "layer": layers,
        "y": np.linspace(grid.max_y, grid.min_y, grid.height, dtype="float64"),
        "x": np.linspace(grid.min_x, grid.max_x, grid.width, dtype="float64"),
    }
    data_vars = {}
    for semantic_type, definition in definitions.items():
        idx = int(definition["idx"])
        variable = str(definition["variable"])
        selected = [item for item in records if item.idx == idx and start_hour <= item.hour <= end_hour]
        by_hour_layer = {(item.hour, item.layer): item.path for item in selected}
        data = np.full((len(hours), len(layers), grid.height, grid.width), np.nan, dtype="float32")
        for t_index, hour in enumerate(hours):
            for layer_index, layer in enumerate(layers):
                path = by_hour_layer.get((hour, layer))
                if path is None:
                    continue
                arr = tifffile.imread(str(path)).astype("float32")
                arr[arr == -999.0] = np.nan
                data[t_index, layer_index] = arr
        data_vars[variable] = (("time", "layer", "y", "x"), data)
        print(f"{semantic_type}: loaded {len(selected)} TIF files as {variable}")

    ds = xr.Dataset(
        data_vars,
        coords=coords,
        attrs={
            "product": "changtan_base_zarr_real",
            "source_product": "changtan_efdc_hourtif_real",
            "source": str(tif_dir.resolve()),
            "vertical_reference": json.dumps(
                {"layer_depth_m": LAYER_DEPTH_MAP, "layer_order": "bottom_to_surface"},
                ensure_ascii=False,
            ),
            "time_basis": "model_hour",
            "start_hour": int(start_hour),
            "end_hour": int(end_hour),
        },
    )
    output_zarr.parent.mkdir(parents=True, exist_ok=True)
    encoding = {name: {"chunks": (24, len(layers), 64, 64)} for name in data_vars}
    ds.to_zarr(output_zarr, mode="w", consolidated=True, encoding=encoding)
    catalog_path = output_zarr.parent / "catalog.json"
    catalog = ODCCatalog(catalog_path)
    catalog.register_product("changtan_base_zarr_real", {"name": "changtan_base_zarr_real", "format": "Zarr"})
    catalog.register_datasets(
        [
            DatasetRecord(
                id=deterministic_dataset_uuid(
                    "changtan_base_zarr_real",
                    output_zarr.resolve(),
                    str(coords["time"][0]),
                    str(coords["time"][-1]),
                ),
                product="changtan_base_zarr_real",
                uri=str(output_zarr.resolve()),
                data_type="model",
                variables=list(data_vars),
                properties={"odc:file_format": "Zarr"},
                time_start=str(coords["time"][0]),
                time_end=str(coords["time"][-1]),
            )
        ]
    )
    return {
        "base_zarr": str(output_zarr),
        "catalog": str(catalog_path),
        "variables": list(data_vars),
        "hours": len(hours),
        "layers": len(layers),
        "shape_yx": [grid.height, grid.width],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the real Changtan EFDC Base Zarr from hourly TIF files.")
    parser.add_argument("--tif-dir", default=None)
    parser.add_argument("--output-zarr", default="real_output/base_changtan_efdc_169h.zarr")
    parser.add_argument("--start-hour", type=int, default=1)
    parser.add_argument("--end-hour", type=int, default=169)
    args = parser.parse_args()
    result = build_real_base_zarr(
        tif_dir=Path(args.tif_dir) if args.tif_dir else default_efdc_root(Path.cwd()) / "hourtif",
        output_zarr=Path(args.output_zarr),
        start_hour=args.start_hour,
        end_hour=args.end_hour,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
