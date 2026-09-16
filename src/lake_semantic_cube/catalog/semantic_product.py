from __future__ import annotations

from pathlib import Path

import xarray as xr

from lake_semantic_cube.io.storage import open_zarr_like

from .eo3 import deterministic_dataset_uuid


MEASUREMENTS = [
    "occurrence",
    "z_top",
    "z_bottom",
    "thickness",
    "core_depth",
    "segment_count",
    "layer_start",
    "layer_end",
]


def semantic_dataset_doc(product: str, zarr_path: str | Path) -> dict:
    ds = open_zarr_like(zarr_path)
    time_start = str(ds.time.values[0]) if "time" in ds.coords and ds.sizes.get("time", 0) else None
    time_end = str(ds.time.values[-1]) if "time" in ds.coords and ds.sizes.get("time", 0) else None
    return {
        "id": deterministic_dataset_uuid(
            product,
            zarr_path,
            time_start,
            time_end,
            ds.attrs.get("rule_id"),
            ds.attrs.get("rule_version"),
        ),
        "product": product,
        "uri": str(zarr_path),
        "properties": {
            "semantic:type": ds.attrs.get("semantic_type"),
            "semantic:rule_id": ds.attrs.get("rule_id"),
            "semantic:rule_version": ds.attrs.get("rule_version"),
            "semantic:source_product": ds.attrs.get("source_product"),
            "semantic:primary_segment_policy": ds.attrs.get("primary_segment_policy"),
            "odc:file_format": "Zarr",
        },
        "measurements": {name: {"path": str(zarr_path), "array": name} for name in MEASUREMENTS},
        "time_start": time_start,
        "time_end": time_end,
    }
