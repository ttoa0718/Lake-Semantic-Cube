from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from lake_semantic_cube.catalog.odc import DatasetRecord, ODCCatalog
from lake_semantic_cube.io.storage import open_zarr_like

from .chunks import get_chunk_indices
from .request import BBox, Point, QueryRequest


@dataclass
class QueryPlan:
    query: QueryRequest
    semantic_type: str
    rule_id: str | None
    rule_version: str | None
    semantic_product: str
    semantic_datasets: list[DatasetRecord]
    base_product: str
    base_datasets: list[DatasetRecord]
    time_slice: slice
    spatial_slice: tuple[slice, slice]
    candidate_layers: tuple[int, int] | None
    actual_depth_range: tuple[float, float] | None
    array_slices: dict[str, str]
    zarr_parts: list[str]
    chunk_indices: list[tuple[int, int, int, int]]
    layer_start_array: np.ndarray
    layer_end_array: np.ndarray


def _nearest(values: np.ndarray, value: float) -> int:
    return int(np.nanargmin(np.abs(values.astype("float64") - value)))


def _coord_slice(values: np.ndarray, low: float, high: float) -> slice:
    lo = min(_nearest(values, low), _nearest(values, high))
    hi = max(_nearest(values, low), _nearest(values, high))
    return slice(lo, hi + 1)


class QueryPlanner:
    """Plan semantic to depth to layer to chunk access."""

    def __init__(self, catalog: ODCCatalog, chunk_shape: tuple[int, int, int, int] = (24, 9999, 64, 64)):
        self.catalog = catalog
        self.chunk_shape = chunk_shape

    def plan(self, query: QueryRequest) -> QueryPlan:
        try:
            semantic_records = self.catalog.find_semantic_datasets(query.semantic, time=query.time, space=query.space)
        except TypeError:
            semantic_records = self.catalog.find_semantic_datasets(query.semantic)
        if not semantic_records:
            raise LookupError(f"No semantic dataset registered for {query.semantic}")
        semantic_record = semantic_records[-1]
        semantic = open_zarr_like(semantic_record.uri).sel(time=slice(query.time[0], query.time[1]))

        try:
            base_records = self.catalog.find_base_datasets(
                variables=list(query.variables), product_type=query.product_type, time=query.time, space=query.space
            )
        except TypeError:
            base_records = self.catalog.find_base_datasets(
                variables=list(query.variables), product_type=query.product_type
            )
        if not base_records:
            source_product = semantic.attrs.get("source_product")
            try:
                base_records = self.catalog.find_base_datasets(
                    product=source_product, variables=list(query.variables), time=query.time, space=query.space
                )
            except TypeError:
                base_records = self.catalog.find_base_datasets(product=source_product, variables=list(query.variables))
        if not base_records:
            raise LookupError("No base dataset found for semantic query")
        base_record = base_records[-1]
        base = open_zarr_like(base_record.uri).sel(time=slice(query.time[0], query.time[1]))
        if "latitude" in base.dims:
            base = base.rename({"latitude": "y", "longitude": "x"})
        if "z" in base.dims:
            base = base.rename({"z": "layer"})

        if isinstance(query.space, Point):
            sy = _nearest(semantic["y"].values, query.space.y)
            sx = _nearest(semantic["x"].values, query.space.x)
            spatial = (slice(sy, sy + 1), slice(sx, sx + 1))
        elif isinstance(query.space, BBox):
            spatial = (
                _coord_slice(semantic["y"].values, query.space.min_y, query.space.max_y),
                _coord_slice(semantic["x"].values, query.space.min_x, query.space.max_x),
            )
        else:
            raise TypeError("Unsupported spatial request")

        sem_sub = semantic.isel(y=spatial[0], x=spatial[1])
        starts = sem_sub["layer_start"].to_numpy()
        ends = sem_sub["layer_end"].to_numpy()
        valid_starts = starts[starts >= 0]
        valid_ends = ends[ends >= 0]
        z_top = sem_sub["z_top"].to_numpy()
        z_bottom = sem_sub["z_bottom"].to_numpy()
        valid_depths = np.concatenate([z_top[np.isfinite(z_top)], z_bottom[np.isfinite(z_bottom)]])
        candidate = None
        actual_depth_range = None
        chunks: list[tuple[int, int, int, int]] = []
        if valid_starts.size and valid_ends.size:
            candidate = (int(valid_starts.min()), int(valid_ends.max()))
            if valid_depths.size:
                actual_depth_range = (float(valid_depths.min()), float(valid_depths.max()))
            chunks = get_chunk_indices(
                (0, max(0, sem_sub.sizes["time"] - 1)),
                candidate,
                (spatial[0].start or 0, (spatial[0].stop or 1) - 1),
                (spatial[1].start or 0, (spatial[1].stop or 1) - 1),
                self.chunk_shape,
            )

        return QueryPlan(
            query=query,
            semantic_type=query.semantic,
            rule_id=semantic.attrs.get("rule_id"),
            rule_version=semantic.attrs.get("rule_version"),
            semantic_product=semantic_record.product,
            semantic_datasets=semantic_records,
            base_product=base_record.product,
            base_datasets=base_records,
            time_slice=slice(query.time[0], query.time[1]),
            spatial_slice=spatial,
            candidate_layers=candidate,
            actual_depth_range=actual_depth_range,
            array_slices={
                "time": f"{query.time[0]}:{query.time[1]}",
                "layer": f"{candidate[0]}:{candidate[1] + 1}" if candidate else "",
                "y": f"{spatial[0].start}:{spatial[0].stop}",
                "x": f"{spatial[1].start}:{spatial[1].stop}",
            },
            zarr_parts=[str(Path(base_record.uri))],
            chunk_indices=chunks,
            layer_start_array=starts,
            layer_end_array=ends,
        )
