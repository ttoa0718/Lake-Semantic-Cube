from __future__ import annotations

from pathlib import Path

from lake_semantic_cube.io.storage import open_zarr_like

from .eo3 import deterministic_dataset_uuid


def base_dataset_doc(product: str, zarr_path: str | Path, data_type: str = "model") -> dict:
    """Create an EO3-like metadata document for a base environmental Zarr product."""
    ds = open_zarr_like(zarr_path)
    time_start = str(ds.time.values[0]) if "time" in ds.coords and ds.sizes.get("time", 0) else None
    time_end = str(ds.time.values[-1]) if "time" in ds.coords and ds.sizes.get("time", 0) else None
    variables = [name for name in ds.data_vars if name not in {"layer_top", "layer_bottom"}]
    return {
        "id": deterministic_dataset_uuid(product, zarr_path, time_start, time_end),
        "product": product,
        "uri": str(zarr_path),
        "properties": {
            "odc:file_format": "Zarr",
            "lake:data_type": data_type,
            "lake:dimensions": list(ds.dims),
        },
        "measurements": {name: {"path": str(zarr_path), "array": name} for name in variables},
        "time_start": time_start,
        "time_end": time_end,
    }
