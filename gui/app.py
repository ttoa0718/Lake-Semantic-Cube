from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import streamlit as st

from lake_semantic_cube.catalog.odc import ODCCatalog
from lake_semantic_cube.catalog.odc_core import OpenDataCubeIndexer, build_odc_docs, register_odc_docs
from lake_semantic_cube.io.efdc_tif import (
    LAYER_DEPTH_MAP,
    SEMANTIC_DEFINITIONS,
    default_efdc_root,
    read_point_timeseries,
    semantic_boundary_timeseries,
)
from lake_semantic_cube.io.profile import ProfileAdapter
from lake_semantic_cube.semantics.parser import parse_rule


ROOT = Path(__file__).resolve().parents[1]
REAL_EFDC_ROOT = default_efdc_root(ROOT)
REAL_HOURTIF = REAL_EFDC_ROOT / "hourtif"
REAL_SEMANTIC_ZARR = ROOT / "real_output" / "semantic_hypoxia_dox_169h.zarr"
REAL_CATALOG = ROOT / "real_output" / "catalog.json"

REAL_SEMANTICS = {key: value for key, value in SEMANTIC_DEFINITIONS.items() if value.get("idx") is not None}


def configure_chinese_font() -> None:
    for font_path in [
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\Deng.ttf"),
        Path(r"C:\Windows\Fonts\simsunb.ttf"),
    ]:
        if font_path.exists():
            font_manager.fontManager.addfont(str(font_path))
            font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return


configure_chinese_font()


def log(message: str) -> None:
    st.session_state.setdefault("runtime_log", []).append(message)


def semantic_options() -> list[str]:
    return list(REAL_SEMANTICS)


def semantic_zarr_path(semantic: str) -> Path:
    return ROOT / str(REAL_SEMANTICS[semantic]["semantic_zarr"])


def scale_for_display(values: np.ndarray, meta: dict) -> np.ndarray:
    raw_min = meta.get("raw_min")
    raw_max = meta.get("raw_max")
    vmin = meta.get("vmin")
    vmax = meta.get("vmax")
    if raw_min is None or raw_max is None or vmin is None or vmax is None:
        return values
    raw_span = float(raw_max) - float(raw_min)
    if raw_span == 0:
        return values
    scaled = (values - float(raw_min)) / raw_span
    return float(vmin) + scaled * (float(vmax) - float(vmin))


def query_real_semantic_zarr_point(semantic: str, x: float, y: float) -> pd.DataFrame:
    path = semantic_zarr_path(semantic)
    if not path.exists():
        return pd.DataFrame()
    try:
        completed = subprocess.run(
            [
                os.environ.get("LAKE_SEMANTIC_PYTHON", sys.executable),
                str(ROOT / "scripts" / "query_semantic_zarr_point.py"),
                "--zarr",
                str(path),
                "--x",
                str(x),
                "--y",
                str(y),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True,
        )
        return pd.DataFrame(json.loads(completed.stdout))
    except Exception as exc:
        log(f"Semantic Zarr bridge failed, falling back to TIF calculation: {exc}")
        return pd.DataFrame()


def real_point_query(semantic: str, x: float, y: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    meta = REAL_SEMANTICS[semantic]
    values = read_point_timeseries(REAL_HOURTIF, x, y, int(meta["idx"]), 1, 169)
    boundary = query_real_semantic_zarr_point(semantic, x, y)
    if boundary.empty:
        boundary = semantic_boundary_timeseries(values, LAYER_DEPTH_MAP, float(meta["threshold"]), str(meta["operator"]))
    return values, boundary


st.set_page_config(page_title="LakeSemCube", layout="wide")
st.title("LakeSemCube")
st.caption("Vertical semantic indexing and multidimensional lake water-environment data access")

tabs = st.tabs(
    [
        "Project & Data",
        "Semantic Rules",
        "Semantic Zarr",
        "ODC Catalog",
        "Point Query",
        "Region Query",
        "Runtime Log",
    ]
)

with tabs[0]:
    st.subheader("Project & Data")
    config_path = st.text_input("Project configuration file", str(ROOT / "configs" / "changtan.real.yaml"))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Load Real Changtan Project", use_container_width=True):
            st.success("Real Changtan project loaded")
            st.json(
                {
                    "efdc_hourtif": str(REAL_HOURTIF),
                    "semantic_zarr": {key: str(semantic_zarr_path(key)) for key in REAL_SEMANTICS},
                    "catalog": str(REAL_CATALOG),
                    "remote_sensing": str(ROOT / "tif" / "S02093_Changtan"),
                    "profile_table": str(ROOT / "剖面浮标.csv"),
                }
            )
            log("Load Real Changtan Project completed")
    with col2:
        if st.button("Scan Data", use_container_width=True):
            tif_count = len(list(REAL_HOURTIF.glob("*.tif")))
            st.write("Real EFDC TIF")
            st.json(
                {
                    "path": str(REAL_HOURTIF),
                    "tif_count": tif_count,
                    "semantic_zarr_exists": {key: semantic_zarr_path(key).exists() for key in REAL_SEMANTICS},
                }
            )
            profile_path = ROOT / "剖面浮标.csv"
            if profile_path.exists():
                try:
                    profile = ProfileAdapter(profile_path, depth_col=None).read()
                    st.write("Profile Data")
                    st.json(
                        {
                            "rows": len(profile.data),
                            "station_col": profile.station_col,
                            "time_col": profile.time_col,
                            "depth_col": profile.depth_col,
                            "variables": list(profile.variable_cols),
                        }
                    )
                except Exception as exc:
                    st.warning(f"Profile preview requires an actual depth column: {exc}")
            log("Scan Data completed")
    st.info("This GUI is configured for real Changtan data. The map click interface is available at http://127.0.0.1:5050.")

with tabs[1]:
    st.subheader("Semantic Rules")
    rule_file = st.selectbox("Load Rule", sorted(str(path) for path in (ROOT / "rules").glob("*.json")))
    raw = Path(rule_file).read_text(encoding="utf-8")
    rule_data = json.loads(raw)
    col1, col2, col3 = st.columns(3)
    with col1:
        semantic_type = st.text_input("Semantic Type", rule_data.get("semantic_type", ""))
        rule_id = st.text_input("Rule ID", rule_data.get("rule_id", ""))
        rule_version = st.text_input("Rule Version", rule_data.get("rule_version", "1.0"))
    with col2:
        variable = st.text_input("Variable", rule_data.get("variables", [{}])[0].get("name", "DOX"))
        operator = st.selectbox("Operator", ["<", "<=", ">", ">=", "==", "between", "gradient_abs_gt"], index=0)
        threshold = st.text_input("Threshold", str(rule_data.get("variables", [{}])[0].get("threshold", 2.0)))
    with col3:
        logic = st.selectbox("Logic", ["AND", "OR"], index=0)
        min_layers = st.number_input("Min Continuous Layers", min_value=1, value=int(rule_data.get("vertical_constraints", {}).get("min_continuous_layers", 1)))
        min_thickness = st.number_input("Min Thickness", min_value=0.0, value=float(rule_data.get("vertical_constraints", {}).get("min_thickness", 0.0)))
    advanced = st.text_area("Advanced JSON View", raw, height=260)
    if st.button("Validate Rule"):
        try:
            rule = parse_rule(json.loads(advanced))
            st.success(f"Valid rule: {rule.semantic_type}")
            log(f"Rule validated: {rule.rule_id}")
        except Exception as exc:
            st.error(str(exc))
            log(f"Rule validation failed: {exc}")

with tabs[2]:
    st.subheader("Semantic Zarr")
    st.json(
        {
            key: {"path": str(semantic_zarr_path(key)), "exists": semantic_zarr_path(key).exists()}
            for key in REAL_SEMANTICS
        }
    )
    st.caption(f"Catalog: {REAL_CATALOG}")
    st.code(
        "$env:PYTHONPATH='src'\n"
        "python scripts\\build_real_hourtif_semantic.py "
        "--tif-dir 'efdc_hour\\hourtif' --output-zarr real_output\\semantic_hypoxia_dox_169h.zarr "
        "--catalog real_output\\catalog.json --semantic hypoxia_layer --start-hour 1 --end-hour 169\n"
        "python scripts\\build_real_hourtif_semantic.py "
        "--tif-dir 'efdc_hour\\hourtif' --output-zarr real_output\\semantic_ammonium_nhx_169h.zarr "
        "--catalog real_output\\catalog.json --semantic ammonium_enriched_layer --start-hour 1 --end-hour 169\n"
        "python scripts\\build_real_hourtif_semantic.py "
        "--tif-dir 'efdc_hour\\hourtif' --output-zarr real_output\\semantic_codmn_169h.zarr "
        "--catalog real_output\\catalog.json --semantic cod_enriched_layer --start-hour 1 --end-hour 169\n"
        "python scripts\\build_real_hourtif_semantic.py "
        "--tif-dir 'efdc_hour\\hourtif' --output-zarr real_output\\semantic_cyanobacteria_chla_169h.zarr "
        "--catalog real_output\\catalog.json --semantic cyanobacteria_enriched_layer --start-hour 1 --end-hour 169",
        language="powershell",
    )

with tabs[3]:
    st.subheader("ODC Catalog")
    datacube_exe = st.text_input("Datacube CLI", os.environ.get("DATACUBE_EXE", "datacube"))
    odc_output_dir = ROOT / "odc_output"
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Test ODC Connection", use_container_width=True):
            try:
                result = OpenDataCubeIndexer(datacube_exe=datacube_exe, cwd=ROOT).product_list()
                st.code(result.stdout or result.stderr)
                log("Real ODC product list executed")
            except Exception as exc:
                st.warning(f"ODC database is not configured or Datacube CLI is unavailable: {exc}")
                log(f"ODC Test Connection failed: {exc}")
    with col2:
        if st.button("Generate ODC YAML", use_container_width=True):
            try:
                paths = build_odc_docs(ROOT, odc_output_dir)
                st.json({key: [str(path) for path in value] for key, value in paths.items()})
                log("Real ODC YAML generated")
            except Exception as exc:
                st.error(str(exc))
                log(f"ODC YAML generation failed: {exc}")
    with col3:
        if st.button("Register in ODC", use_container_width=True):
            try:
                paths = build_odc_docs(ROOT, odc_output_dir)
                results = register_odc_docs(paths, datacube_exe, ROOT)
                st.dataframe(pd.DataFrame(results))
                log("Real ODC registration executed")
            except Exception as exc:
                st.error(str(exc))
                log(f"ODC registration failed: {exc}")
    if st.button("Count semantic datasets"):
        try:
            result = OpenDataCubeIndexer(datacube_exe=datacube_exe, cwd=ROOT).dataset_count("changtan_vertical_semantic_real")
            st.code(result.stdout or result.stderr)
            log("Real ODC semantic dataset count executed")
        except Exception as exc:
            st.warning(f"ODC database is not configured or Datacube CLI is unavailable: {exc}")
            log(f"ODC semantic dataset count failed: {exc}")
    st.write("Local fallback catalog")
    catalog = ODCCatalog(REAL_CATALOG)
    st.dataframe(pd.DataFrame([record.__dict__ for record in catalog.records]))

with tabs[4]:
    st.subheader("Point Query")
    mode = st.radio("Query Mode", ["Semantic Layer"], horizontal=True)
    semantic = st.selectbox("Semantic Type", semantic_options(), format_func=lambda key: REAL_SEMANTICS[key]["label"])
    x = st.number_input("Longitude / X", value=121.031998, format="%.6f")
    y = st.number_input("Latitude / Y", value=28.568300, format="%.6f")
    if mode == "Semantic Layer" and st.button("Run Point Query"):
        values, boundary = real_point_query(semantic, x, y)
        st.write("Real EFDC values")
        st.dataframe(values)
        st.write("Semantic boundary")
        st.dataframe(boundary)
        st.download_button("Download Values CSV", values.to_csv(index=False), "real_point_values.csv")
        st.download_button("Download Semantic Boundary CSV", boundary.to_csv(index=False), "real_point_semantic_boundary.csv")
        fig, ax = plt.subplots(figsize=(8, 4))
        pivot = values.pivot_table(index="layer", columns="hour", values="value")
        depth_labels = [LAYER_DEPTH_MAP.get(int(layer), float(layer)) for layer in pivot.index]
        meta = REAL_SEMANTICS[semantic]
        im = ax.imshow(
            scale_for_display(pivot.to_numpy(), meta),
            aspect="auto",
            origin="upper",
            extent=[float(pivot.columns.min()), float(pivot.columns.max()), max(depth_labels), min(depth_labels)],
            cmap=meta["cmap"],
            vmin=meta["vmin"],
            vmax=meta["vmax"],
        )
        ax.plot(boundary["hour"], boundary["z_top"], color="red", label=meta.get("upper_label", "z_top"))
        ax.plot(boundary["hour"], boundary["z_bottom"], color="black", linestyle="--", label=meta.get("lower_label", "z_bottom"))
        ax.set_xlabel("Model hour")
        ax.set_ylabel("Depth (m)")
        fig.colorbar(im, ax=ax)
        ax.legend()
        st.pyplot(fig)
        log("Real point semantic query completed")

with tabs[5]:
    st.subheader("Region Query")
    st.markdown("[Open real map region query](http://127.0.0.1:5050)")
    st.info("Use the box tool in the map UI. It reads real EFDC TIF files and computes semantic thickness maps for the selected region.")

with tabs[6]:
    st.subheader("Runtime Log")
    for item in st.session_state.get("runtime_log", []):
        st.write(item)
