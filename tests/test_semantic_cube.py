from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from lake_semantic_cube.catalog.eo3 import deterministic_dataset_uuid
from lake_semantic_cube.catalog.odc import DatasetRecord, ODCCatalog
from lake_semantic_cube.cli import run_demo
from lake_semantic_cube.io.model_tif import (
    datetime_to_model_hour,
    model_hour_to_datetime,
    parse_model_tif_filename,
)
from lake_semantic_cube.io.model_zarr import build_base_zarr_from_arrays, partition_time
from lake_semantic_cube.io.profile import ProfileAdapter, profile_depth_mask
from lake_semantic_cube.io.surface import build_surface_zarr_from_arrays
from lake_semantic_cube.io.profile_zarr import ProfileProduct
from lake_semantic_cube.io.surface_zarr import SurfaceProduct
from lake_semantic_cube.query.actual_depth import query_actual_depth
from lake_semantic_cube.query.chunks import get_chunk_indices
from lake_semantic_cube.query.planner import QueryPlanner
from lake_semantic_cube.query.point import query_point
from lake_semantic_cube.query.region import query_region
from lake_semantic_cube.query.request import BBox, Point, QueryRequest
from lake_semantic_cube.semantic_product.metadata import semantic_attrs
from lake_semantic_cube.semantic_product.writer import write_semantic_zarr
from lake_semantic_cube.semantics.builder import build_semantic_zarr
from lake_semantic_cube.semantics.evaluator import SemanticEvaluator
from lake_semantic_cube.semantics.parser import parse_rule
from lake_semantic_cube.semantics.segment import detect_segments, primary_segment
from lake_semantic_cube.vertical.mapper import layer_bounds_grid
from lake_semantic_cube.vertical.reference import VerticalReference


def make_base() -> tuple[xr.Dataset, np.ndarray]:
    times = pd.date_range("2025-01-01", periods=4, freq="h")
    coords = {"time": times, "layer": np.arange(4), "y": np.arange(3), "x": np.arange(3)}
    dox = np.full((4, 4, 3, 3), 8.0, dtype="float32")
    dox[:, 2:, :, :] = 1.0
    dox[:, 0, 0, 0] = 1.0
    dox[:, 2:, 0, 0] = 8.0
    chl = np.arange(dox.size, dtype="float32").reshape(dox.shape)
    temp = np.zeros_like(dox)
    temp[:, 0, :, :] = 24.0
    temp[:, 1, :, :] = 23.0
    temp[:, 2, :, :] = 18.0
    temp[:, 3, :, :] = 17.0
    ds = xr.Dataset(
        {
            "DOX": (("time", "layer", "y", "x"), dox),
            "CHL": (("time", "layer", "y", "x"), chl),
            "TEMP": (("time", "layer", "y", "x"), temp),
        },
        coords=coords,
    )
    water_depth = np.array([[2.0, 4.0, 6.0], [3.0, 5.0, 7.0], [4.0, 6.0, 8.0]])
    return ds, water_depth


def hypoxia_rule(min_layers: int = 2, min_thickness: float = 1.0):
    return parse_rule(
        {
            "rule_id": "hypoxia_test",
            "rule_version": "1",
            "semantic_type": "hypoxia_layer",
            "variables": [{"name": "DOX", "operator": "<", "threshold": 2.0}],
            "vertical_constraints": {
                "min_continuous_layers": min_layers,
                "min_thickness": min_thickness,
            },
        }
    )


def test_filename_time_and_variable_config():
    parsed = parse_model_tif_filename("WQ_TSK_9_DOM_18_14.tif")
    assert parsed == {"layer": 9, "hour": 18, "variable": 14}
    start = datetime(2025, 1, 1)
    assert model_hour_to_datetime(start, 1, hour_base=1) == start
    assert datetime_to_model_hour(start, start, hour_base=1) == 1


def test_base_zarr_and_partition(tmp_path):
    ds, _ = make_base()
    path = tmp_path / "base.zarr"
    written = build_base_zarr_from_arrays(
        {name: ds[name].to_numpy() for name in ds.data_vars},
        ds.time.values,
        ds.layer.values,
        ds.y.values,
        ds.x.values,
        path,
        chunks={"time": 2, "layer": "all", "y": 2, "x": 2},
    )
    assert path.exists()
    parts = partition_time(written, tmp_path / "parts", hours_per_partition=2)
    assert len(parts) == 2


def test_surface_zarr_and_profile_adapter(tmp_path):
    surface_path = tmp_path / "surface.zarr"
    surface = build_surface_zarr_from_arrays(
        {"CHL": np.ones((2, 3, 4), dtype="float32")},
        pd.date_range("2025-01-01", periods=2, freq="h"),
        np.arange(3),
        np.arange(4),
        surface_path,
    )
    assert surface.attrs["vertical_support"] == "surface"
    csv_path = tmp_path / "profile.csv"
    pd.DataFrame(
        {
            "station": ["A", "A", "B"],
            "time": ["2025-01-01", "2025-01-01", "2025-01-02"],
            "actual_depth": [0.5, 2.0, 5.0],
            "DOX": [8.0, 1.5, 7.0],
        }
    ).to_csv(csv_path, index=False)
    profile = ProfileAdapter(csv_path).read()
    assert profile.variable_cols == ("DOX",)
    assert len(profile.match_semantic_interval(1.0, 3.0)) == 1
    assert profile_depth_mask(np.array([0.5, 2.0, 5.0]), 1.0, 3.0).tolist() == [False, True, False]


def test_vertical_reference_and_dynamic_bathymetry():
    ref = VerticalReference.uniform_relative(4)
    assert ref.layer_to_depth(0, 8.0) == (0.0, 2.0)
    assert ref.depth_to_layers(2.0, 4.0, 8.0) == [1]
    explicit = VerticalReference.explicit([0.0, 1.0, 3.0])
    assert explicit.layer_to_depth(1, 9.0) == (1.0, 3.0)
    sigma = VerticalReference.sigma([0.0, 0.25, 1.0])
    assert sigma.layer_to_depth(1, 8.0) == (2.0, 8.0)
    tops, bottoms = layer_bounds_grid(ref, np.array([[4.0, 8.0]]))
    assert tops.shape == (4, 1, 2)
    assert bottoms[0, 0, 1] == 2.0


def test_rule_parsing_invalid_absolute_percentile_gradient_and_logic():
    rule = hypoxia_rule()
    assert rule.variable_names == ["DOX"]
    with pytest.raises(ValueError):
        parse_rule({"rule_id": "bad", "rule_version": "1", "semantic_type": "x", "variables": []})
    percentile = parse_rule(
        {
            "rule_id": "chl_p90",
            "rule_version": "1",
            "semantic_type": "algal",
            "variables": [{"name": "CHL", "operator": ">", "threshold_type": "percentile", "threshold": 90}],
        }
    )
    gradient = parse_rule(
        {
            "rule_id": "thermo",
            "rule_version": "1",
            "semantic_type": "thermocline",
            "variables": [{"name": "TEMP", "operator": "gradient_abs_gt", "threshold": 0.5}],
        }
    )
    assert percentile.variables[0].threshold_type == "percentile"
    assert gradient.variables[0].operator == "gradient_abs_gt"
    either = parse_rule(
        {
            "rule_id": "or",
            "rule_version": "1",
            "semantic_type": "either",
            "logic": "OR",
            "variables": [
                {"name": "DOX", "operator": "<", "threshold": 2.0},
                {"name": "CHL", "operator": ">", "threshold": 1e9},
            ],
        }
    )
    assert either.logic == "OR"


def test_segments_multiple_primary_and_constraints():
    mask = np.array([True, False, True, True, True])
    tops = np.array([0, 1, 2, 3, 4], dtype=float)
    bottoms = tops + 1
    segments = detect_segments(mask, tops, bottoms, min_continuous_layers=1, min_thickness=1.0)
    assert len(segments) == 2
    assert primary_segment(segments).layer_start == 2
    assert detect_segments(mask, tops, bottoms, min_continuous_layers=4) == []


def test_semantic_evaluator_outputs_nan_and_primary_policy():
    ds, water_depth = make_base()
    semantic = SemanticEvaluator(hypoxia_rule(), VerticalReference.uniform_relative(4)).evaluate(ds, water_depth)
    assert int(semantic["occurrence"].isel(time=0, y=1, x=1)) == 1
    assert np.isnan(float(semantic["z_top"].isel(time=0, y=0, x=0)))
    assert int(semantic["layer_start"].isel(time=0, y=1, x=1)) == 2
    assert int(semantic["layer_end"].isel(time=0, y=1, x=1)) == 3
    assert float(semantic["thickness"].isel(time=0, y=1, x=1)) == pytest.approx(2.5)


def test_percentile_and_gradient_evaluation():
    ds, water_depth = make_base()
    chl_rule = parse_rule(
        {
            "rule_id": "chl",
            "rule_version": "1",
            "semantic_type": "algal",
            "variables": [{"name": "CHL", "operator": ">", "threshold_type": "percentile", "threshold": 90}],
        }
    )
    chl_sem = SemanticEvaluator(chl_rule, VerticalReference.uniform_relative(4)).evaluate(ds, water_depth)
    assert int(chl_sem["occurrence"].sum()) > 0
    thermo_rule = parse_rule(
        {
            "rule_id": "thermo",
            "rule_version": "1",
            "semantic_type": "thermocline",
            "variables": [{"name": "TEMP", "operator": "gradient_abs_gt", "threshold": 0.5}],
        }
    )
    thermo_sem = SemanticEvaluator(thermo_rule, VerticalReference.uniform_relative(4)).evaluate(ds, water_depth)
    assert int(thermo_sem["occurrence"].sum()) > 0


def test_semantic_zarr_metadata_uuid_and_query_chain(tmp_path):
    ds, water_depth = make_base()
    base_path = tmp_path / "base.zarr"
    build_base_zarr_from_arrays(
        {name: ds[name].to_numpy() for name in ds.data_vars},
        ds.time.values,
        ds.layer.values,
        ds.y.values,
        ds.x.values,
        base_path,
        chunks={"time": 2, "layer": "all", "y": 2, "x": 2},
    )
    semantic_path = tmp_path / "semantic.zarr"
    rule = hypoxia_rule()
    semantic = build_semantic_zarr(
        base_path,
        semantic_path,
        rule,
        VerticalReference.uniform_relative(4),
        water_depth,
        "test_model",
    )
    attrs = semantic_attrs(rule, "test_model", VerticalReference.uniform_relative(4))
    assert attrs["primary_segment_policy"] == "thickest"
    assert semantic_path.exists()
    write_semantic_zarr(semantic, tmp_path / "semantic_copy.zarr")
    id1 = deterministic_dataset_uuid("p", semantic_path, "a", "b", "r", "1")
    id2 = deterministic_dataset_uuid("p", semantic_path, "a", "b", "r", "1")
    assert id1 == id2

    catalog = ODCCatalog(tmp_path / "catalog.json")
    catalog.add(
        DatasetRecord(id="base", product="test_model", uri=str(base_path), data_type="model", variables=list(ds.data_vars))
    )
    catalog.add(
        DatasetRecord(
            id="semantic",
            product="test_semantic",
            uri=str(semantic_path),
            data_type="semantic",
            variables=list(semantic.data_vars),
            properties={"semantic:type": "hypoxia_layer"},
        )
    )
    request = QueryRequest(
        time=(str(ds.time.values[0]), str(ds.time.values[-1])),
        space=Point(1.0, 1.0),
        semantic="hypoxia_layer",
        variables=("DOX",),
        product_type="model",
    )
    plan = QueryPlanner(catalog, chunk_shape=(2, 4, 2, 2)).plan(request)
    assert plan.candidate_layers == (2, 3)
    assert plan.chunk_indices
    point = query_point(plan)
    assert len(point) == 4
    assert point["occurrence"].sum() == 4
    region_plan = QueryPlanner(catalog, chunk_shape=(2, 4, 2, 2)).plan(
        QueryRequest(
            time=(str(ds.time.values[0]), str(ds.time.values[-1])),
            space=BBox(0.0, 0.0, 2.0, 2.0),
            semantic="hypoxia_layer",
            variables=("DOX",),
            product_type="model",
        )
    )
    region = query_region(region_plan)
    assert int(region.loc[0, "count"]) > 0
    actual = query_actual_depth(
        str(base_path),
        (str(ds.time.values[0]), str(ds.time.values[-1])),
        Point(1.0, 1.0),
        3.0,
        ("DOX",),
        VerticalReference.uniform_relative(4),
        water_depth=4.0,
    )
    assert "mapped_layer" in actual.columns
    assert len(actual) == 4


def test_chunk_indices_surface_profile_and_demo(tmp_path):
    chunks = get_chunk_indices((0, 3), (2, 3), (0, 7), (0, 7), (2, 4, 4, 4))
    assert (0, 0, 0, 0) in chunks
    assert SurfaceProduct.matches_semantic_interval(0.0, 1.0)
    assert not SurfaceProduct.matches_semantic_interval(1.0, 2.0)
    assert ProfileProduct.depth_mask(np.array([0.5, 2.0, 5.0]), 1.0, 3.0).tolist() == [False, True, False]
    summary = run_demo(tmp_path / "demo")
    assert summary["point_rows"] == 4
    assert summary["region_rows"] == 1
