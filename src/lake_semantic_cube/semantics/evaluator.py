from __future__ import annotations

import operator

import numpy as np
import xarray as xr

from lake_semantic_cube.vertical.mapper import layer_bounds_grid
from lake_semantic_cube.vertical.reference import VerticalReference

from .rule import SemanticRule, VariableCondition
from .segment import detect_segments, primary_segment

OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}


def normalize_model_dims(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "z" in ds.dims:
        rename["z"] = "layer"
    if "latitude" in ds.dims:
        rename["latitude"] = "y"
    if "longitude" in ds.dims:
        rename["longitude"] = "x"
    return ds.rename(rename) if rename else ds


class SemanticEvaluator:
    """Evaluate JSON-defined semantic rules against base model data."""

    def __init__(self, rule: SemanticRule, vertical_reference: VerticalReference):
        self.rule = rule
        self.vertical_reference = vertical_reference

    def _threshold(self, condition: VariableCondition, data: xr.DataArray) -> float | list[float]:
        if condition.threshold_type == "absolute":
            return condition.threshold
        if condition.threshold_type == "percentile":
            if condition.percentile_scope != "global":
                raise NotImplementedError("Only dataset/global percentile scope is implemented")
            return float(np.nanpercentile(data.to_numpy(), float(condition.threshold)))
        raise ValueError(f"Unsupported threshold_type: {condition.threshold_type}")

    def _condition_mask(
        self,
        ds: xr.Dataset,
        condition: VariableCondition,
        layer_tops: np.ndarray,
        layer_bottoms: np.ndarray,
    ) -> np.ndarray:
        if condition.name not in ds:
            raise KeyError(f"Rule variable {condition.name!r} not present in base data")
        values = ds[condition.name].transpose("time", "layer", "y", "x").to_numpy()
        threshold = self._threshold(condition, ds[condition.name])
        if condition.operator in OPS:
            return OPS[condition.operator](values, float(threshold))
        if condition.operator == "between":
            lo, hi = threshold
            return (values >= float(lo)) & (values <= float(hi))
        if condition.operator == "gradient_abs_gt":
            centers = (layer_tops + layer_bottoms) / 2.0
            grad = np.full_like(values, np.nan, dtype="float64")
            for index in np.ndindex(values.shape[0], values.shape[2], values.shape[3]):
                t, y, x = index
                z = centers[:, y, x]
                profile = values[t, :, y, x].astype("float64")
                if np.isfinite(profile).sum() >= 2:
                    grad[t, :, y, x] = np.gradient(profile, z)
            return np.abs(grad) > float(threshold)
        raise ValueError(f"Unsupported operator: {condition.operator}")

    def evaluate(self, ds: xr.Dataset, water_depth: float | np.ndarray) -> xr.Dataset:
        base = normalize_model_dims(ds)
        required_dims = {"time", "layer", "y", "x"}
        if not required_dims.issubset(base.dims):
            raise ValueError(f"Base dataset must include dimensions {sorted(required_dims)}")
        if np.isscalar(water_depth):
            depth_grid = np.full((base.sizes["y"], base.sizes["x"]), float(water_depth), dtype="float64")
        else:
            depth_grid = np.asarray(water_depth, dtype="float64")
            if depth_grid.shape != (base.sizes["y"], base.sizes["x"]):
                raise ValueError("water_depth grid must have shape y, x")
        layer_tops, layer_bottoms = layer_bounds_grid(self.vertical_reference, depth_grid)

        condition_masks = [
            self._condition_mask(base, condition, layer_tops, layer_bottoms)
            for condition in self.rule.variables
        ]
        combined = condition_masks[0]
        for mask in condition_masks[1:]:
            combined = (combined & mask) if self.rule.logic == "AND" else (combined | mask)
        combined = np.nan_to_num(combined, nan=False).astype(bool)

        shape3 = (base.sizes["time"], base.sizes["y"], base.sizes["x"])
        occurrence = np.zeros(shape3, dtype="uint8")
        z_top = np.full(shape3, np.nan, dtype="float32")
        z_bottom = np.full(shape3, np.nan, dtype="float32")
        thickness = np.full(shape3, np.nan, dtype="float32")
        core_depth = np.full(shape3, np.nan, dtype="float32")
        segment_count = np.zeros(shape3, dtype="int16")
        layer_start = np.full(shape3, -1, dtype="int16")
        layer_end = np.full(shape3, -1, dtype="int16")
        semantic_mask = np.zeros(combined.shape, dtype="uint8")

        vc = self.rule.vertical_constraints
        for t in range(base.sizes["time"]):
            for yy in range(base.sizes["y"]):
                for xx in range(base.sizes["x"]):
                    segments = detect_segments(
                        combined[t, :, yy, xx],
                        layer_tops[:, yy, xx],
                        layer_bottoms[:, yy, xx],
                        vc.min_continuous_layers,
                        vc.min_thickness,
                    )
                    segment_count[t, yy, xx] = len(segments)
                    chosen = primary_segment(segments)
                    if chosen is None:
                        continue
                    occurrence[t, yy, xx] = 1
                    z_top[t, yy, xx] = chosen.z_top
                    z_bottom[t, yy, xx] = chosen.z_bottom
                    thickness[t, yy, xx] = chosen.thickness
                    core_depth[t, yy, xx] = chosen.core_depth
                    layer_start[t, yy, xx] = chosen.layer_start
                    layer_end[t, yy, xx] = chosen.layer_end
                    semantic_mask[t, chosen.layer_start : chosen.layer_end + 1, yy, xx] = 1

        return xr.Dataset(
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
            coords={
                "time": base["time"].values,
                "layer": base["layer"].values,
                "y": base["y"].values,
                "x": base["x"].values,
            },
        )
