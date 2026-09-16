from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from lake_semantic_cube.catalog.eo3 import deterministic_dataset_uuid
from lake_semantic_cube.catalog.odc import DatasetRecord, ODCCatalog
from lake_semantic_cube.catalog.semantic_product import semantic_dataset_doc
from lake_semantic_cube.io.model_zarr import build_base_zarr_from_arrays
from lake_semantic_cube.query.planner import QueryPlanner
from lake_semantic_cube.query.point import query_point
from lake_semantic_cube.query.region import query_region
from lake_semantic_cube.query.request import BBox, Point, QueryRequest
from lake_semantic_cube.semantics.builder import build_semantic_zarr
from lake_semantic_cube.semantics.parser import load_rule
from lake_semantic_cube.vertical.reference import VerticalReference


def _demo_arrays() -> tuple[dict[str, np.ndarray], pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    times = pd.date_range("2025-01-01", periods=4, freq="h")
    layers = np.arange(4)
    y = np.arange(8, dtype="float64")
    x = np.arange(8, dtype="float64")
    water_depth = np.linspace(4.0, 8.0, 64).reshape(8, 8)
    dox = np.full((4, 4, 8, 8), 8.0, dtype="float32")
    dox[:, 2:, 2:7, 2:7] = 1.0
    dox[2:, 1, 4:6, 4:6] = 1.5
    chl = np.arange(dox.size, dtype="float32").reshape(dox.shape)
    temp = np.zeros_like(dox)
    temp[:, 0, :, :] = 24.0
    temp[:, 1, :, :] = 23.0
    temp[:, 2, :, :] = 18.0
    temp[:, 3, :, :] = 17.0
    return {"DOX": dox, "CHL": chl, "TEMP": temp}, times, layers, y, x, water_depth


def run_demo(output_dir: str | Path = "demo_output") -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    arrays, times, layers, y, x, water_depth = _demo_arrays()
    base_path = out / "base_model.zarr"
    semantic_path = out / "semantic_hypoxia.zarr"
    catalog_path = out / "catalog.json"
    base = build_base_zarr_from_arrays(
        arrays,
        times,
        layers,
        y,
        x,
        base_path,
        chunks={"time": 2, "layer": "all", "y": 4, "x": 4},
        attrs={"product": "demo_model", "start_time": str(times[0])},
    )
    rule = load_rule(Path("rules/hypoxia.json"))
    vertical = VerticalReference.uniform_relative(layer_count=4, layer_order="surface_to_bottom")
    semantic = build_semantic_zarr(base_path, semantic_path, rule, vertical, water_depth, "demo_model")

    catalog = ODCCatalog(catalog_path)
    catalog.add(
        DatasetRecord(
            id=deterministic_dataset_uuid("demo_model", base_path, str(base.time.values[0]), str(base.time.values[-1])),
            product="demo_model",
            uri=str(base_path),
            data_type="model",
            variables=list(base.data_vars),
            time_start=str(base.time.values[0]),
            time_end=str(base.time.values[-1]),
        )
    )
    sem_doc = semantic_dataset_doc("demo_semantic", semantic_path)
    catalog.add(
        DatasetRecord(
            id=sem_doc["id"],
            product="demo_semantic",
            uri=str(semantic_path),
            data_type="semantic",
            variables=list(semantic.data_vars),
            properties=sem_doc["properties"],
            time_start=sem_doc["time_start"],
            time_end=sem_doc["time_end"],
        )
    )

    planner = QueryPlanner(catalog, chunk_shape=(2, 4, 4, 4))
    request = QueryRequest(
        time=(str(times[0]), str(times[-1])),
        space=Point(4.0, 4.0),
        semantic="hypoxia_layer",
        variables=("DOX",),
        product_type="model",
    )
    point_plan = planner.plan(request)
    point_result = query_point(point_plan)
    region_plan = planner.plan(
        QueryRequest(
            time=(str(times[0]), str(times[-1])),
            space=BBox(2.0, 2.0, 6.0, 6.0),
            semantic="hypoxia_layer",
            variables=("DOX",),
            product_type="model",
        )
    )
    region_result = query_region(region_plan)
    point_csv = out / "point_query.csv"
    region_csv = out / "region_query.csv"
    point_result.to_csv(point_csv, index=False)
    region_result.to_csv(region_csv, index=False)
    summary = {
        "base_zarr": str(base_path),
        "semantic_zarr": str(semantic_path),
        "catalog": str(catalog_path),
        "point_rows": int(len(point_result)),
        "region_rows": int(len(region_result)),
        "chunk_indices": point_plan.chunk_indices,
        "point_query_csv": str(point_csv),
        "region_query_csv": str(region_csv),
    }
    (out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lake-semantic-cube")
    sub = parser.add_subparsers(dest="command")
    demo_p = sub.add_parser("demo", help="Run the synthetic end-to-end semantic indexing demo")
    demo_p.add_argument("--output", default="demo_output")
    sub.add_parser("build-base", help="Build Base Zarr from configured inputs")
    real_base_p = sub.add_parser("build-real-base", help="Build real Changtan EFDC Base Zarr from hourly TIF files")
    real_base_p.add_argument("--tif-dir", default=None)
    real_base_p.add_argument("--output-zarr", default="real_output/base_changtan_efdc_169h.zarr")
    real_base_p.add_argument("--start-hour", type=int, default=1)
    real_base_p.add_argument("--end-hour", type=int, default=169)
    sub.add_parser("build-surface", help="Build Surface Zarr from configured inputs")
    sub.add_parser("build-semantic", help="Build Semantic Zarr from Base Zarr and a JSON rule")
    odc_p = sub.add_parser("index-odc", help="Generate or register real Open Data Cube metadata")
    odc_p.add_argument("--output-dir", default="odc_output")
    odc_p.add_argument("--datacube-exe", default=None)
    odc_p.add_argument("--register", action="store_true")
    sub.add_parser("plan", help="Plan semantic to depth to layer to chunk access")
    sub.add_parser("plan-query", help="Plan semantic to depth to layer to chunk access")
    sub.add_parser("query-point", help="Run a semantic point query")
    sub.add_parser("query-region", help="Run a semantic region query")
    sub.add_parser("query-actual-depth", help="Run an actual-depth point query")
    gui_p = sub.add_parser("gui", help="Start the Streamlit GUI")
    gui_p.add_argument("--port", type=int, default=8501)
    ui_p = sub.add_parser("ui", help="Start the local semantic-layer exploration UI")
    ui_p.add_argument("--host", default="127.0.0.1")
    ui_p.add_argument("--port", type=int, default=5050)
    args = parser.parse_args(argv)
    if args.command == "demo":
        print(json.dumps(run_demo(args.output), indent=2))
    elif args.command == "gui":
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(Path("gui") / "app.py"),
                "--server.port",
                str(args.port),
            ],
            check=False,
        )
    elif args.command == "ui":
        from lake_semantic_cube.ui.app import run_ui

        run_ui(host=args.host, port=args.port)
    elif args.command == "index-odc":
        from lake_semantic_cube.catalog.odc_core import build_odc_docs, register_odc_docs

        root = Path.cwd()
        paths = build_odc_docs(root, root / args.output_dir)
        payload = {
            "products": [str(path) for path in paths["products"]],
            "datasets": [str(path) for path in paths["datasets"]],
        }
        if args.register:
            payload["registration"] = register_odc_docs(paths, args.datacube_exe, root)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.command == "build-real-base":
        from lake_semantic_cube.io.efdc_tif import default_efdc_root
        from scripts.build_real_base_zarr import build_real_base_zarr

        root = Path.cwd()
        tif_dir = Path(args.tif_dir) if args.tif_dir else default_efdc_root(root) / "hourtif"
        payload = build_real_base_zarr(
            tif_dir=tif_dir,
            output_zarr=Path(args.output_zarr),
            start_hour=args.start_hour,
            end_hour=args.end_hour,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.command is None:
        parser.print_help()
    else:
        raise SystemExit(f"{args.command} is a reserved CLI command; use demo for the packaged runnable workflow.")
