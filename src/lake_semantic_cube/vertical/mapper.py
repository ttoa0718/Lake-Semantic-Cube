from __future__ import annotations

import numpy as np

from .reference import VerticalReference


def layer_bounds_grid(reference: VerticalReference, water_depth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return layer top and bottom arrays shaped layer, y, x."""
    depth = np.asarray(water_depth, dtype="float64")
    tops = np.zeros((reference.n_layers, *depth.shape), dtype="float64")
    bottoms = np.zeros_like(tops)
    for index in np.ndindex(depth.shape):
        t, b = reference.all_layer_bounds(float(depth[index]))
        tops[(slice(None), *index)] = t
        bottoms[(slice(None), *index)] = b
    return tops, bottoms
