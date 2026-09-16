from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from lake_semantic_cube.io.storage import open_zarr_like
from lake_semantic_cube.semantic_product.writer import semantic_attrs, write_semantic_zarr
from lake_semantic_cube.vertical.reference import VerticalReference

from .evaluator import SemanticEvaluator
from .rule import SemanticRule


def build_semantic_zarr(
    base_zarr: str | Path,
    output_zarr: str | Path,
    rule: SemanticRule,
    vertical_reference: VerticalReference,
    water_depth: float | np.ndarray,
    source_product: str,
) -> xr.Dataset:
    base = open_zarr_like(base_zarr)
    semantic = SemanticEvaluator(rule, vertical_reference).evaluate(base, water_depth)
    semantic.attrs.update(semantic_attrs(rule, source_product, vertical_reference))
    write_semantic_zarr(semantic, output_zarr)
    return semantic
