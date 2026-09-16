from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class VerticalReference:
    """Map model layers to actual depth intervals below the water surface.

    Supported definitions:
    - explicit: absolute depth edges in metres below surface.
    - sigma: relative depth edges multiplied by local water depth.
    - uniform_relative: N equal relative layers from surface to bottom.
    """

    type: str
    layer_count: int | None = None
    layer_order: str = "surface_to_bottom"
    depth_edges: Sequence[float] | None = None
    sigma_edges: Sequence[float] | None = None

    @classmethod
    def uniform_relative(
        cls, layer_count: int, layer_order: str = "surface_to_bottom"
    ) -> "VerticalReference":
        return cls(type="uniform_relative", layer_count=layer_count, layer_order=layer_order)

    @classmethod
    def explicit(
        cls, depth_edges: Sequence[float], layer_order: str = "surface_to_bottom"
    ) -> "VerticalReference":
        return cls(type="explicit", depth_edges=depth_edges, layer_order=layer_order)

    @classmethod
    def sigma(
        cls, sigma_edges: Sequence[float], layer_order: str = "surface_to_bottom"
    ) -> "VerticalReference":
        return cls(type="sigma", sigma_edges=sigma_edges, layer_order=layer_order)

    def edges_for_depth(self, water_depth: float) -> np.ndarray:
        if water_depth <= 0:
            raise ValueError("water_depth must be positive")
        if self.type == "explicit":
            if self.depth_edges is None:
                raise ValueError("explicit vertical reference requires depth_edges")
            edges = np.asarray(self.depth_edges, dtype="float64")
        elif self.type == "sigma":
            if self.sigma_edges is None:
                raise ValueError("sigma vertical reference requires sigma_edges")
            edges = np.asarray(self.sigma_edges, dtype="float64") * float(water_depth)
        elif self.type == "uniform_relative":
            if self.layer_count is None:
                raise ValueError("uniform_relative requires layer_count")
            edges = np.linspace(0.0, float(water_depth), int(self.layer_count) + 1)
        else:
            raise ValueError(f"Unsupported vertical reference type: {self.type}")
        if np.any(np.diff(edges) < 0):
            raise ValueError("vertical edges must increase downward from surface")
        return edges

    @property
    def n_layers(self) -> int:
        if self.type == "uniform_relative":
            if self.layer_count is None:
                raise ValueError("layer_count is required")
            return int(self.layer_count)
        edges = self.depth_edges if self.type == "explicit" else self.sigma_edges
        if edges is None:
            raise ValueError("vertical edges are required")
        return len(edges) - 1

    def _edge_index(self, layer: int) -> int:
        if layer < 0 or layer >= self.n_layers:
            raise IndexError(f"layer {layer} outside 0..{self.n_layers - 1}")
        if self.layer_order == "surface_to_bottom":
            return layer
        if self.layer_order == "bottom_to_surface":
            return self.n_layers - layer - 1
        raise ValueError("layer_order must be surface_to_bottom or bottom_to_surface")

    def layer_to_depth(self, layer: int, water_depth: float) -> tuple[float, float]:
        edges = self.edges_for_depth(water_depth)
        i = self._edge_index(layer)
        return float(edges[i]), float(edges[i + 1])

    def all_layer_bounds(self, water_depth: float) -> tuple[np.ndarray, np.ndarray]:
        tops = np.zeros(self.n_layers, dtype="float64")
        bottoms = np.zeros(self.n_layers, dtype="float64")
        for layer in range(self.n_layers):
            tops[layer], bottoms[layer] = self.layer_to_depth(layer, water_depth)
        return tops, bottoms

    def depth_to_layers(self, z_top: float, z_bottom: float, water_depth: float) -> list[int]:
        if np.isnan(z_top) or np.isnan(z_bottom):
            return []
        if z_top > z_bottom:
            raise ValueError("z_top must be <= z_bottom")
        result: list[int] = []
        for layer in range(self.n_layers):
            top, bottom = self.layer_to_depth(layer, water_depth)
            if top < z_bottom and bottom > z_top:
                result.append(layer)
        return result

    def to_metadata(self) -> dict:
        return {
            "type": self.type,
            "layer_count": self.n_layers,
            "layer_order": self.layer_order,
            "depth_edges": list(self.depth_edges) if self.depth_edges is not None else None,
            "sigma_edges": list(self.sigma_edges) if self.sigma_edges is not None else None,
        }
