from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
import tifffile

from lake_semantic_cube.io.efdc_tif import (
    LAYER_DEPTH_MAP,
    SEMANTIC_DEFINITIONS,
    default_efdc_root,
    raster_grid,
    read_point_timeseries,
    scan_efdc_tifs,
    semantic_boundary_timeseries,
)
from lake_semantic_cube.io.storage import open_zarr_like


DEMO_TIME = "2026-01-07 02:40:09"


def _configure_chinese_font() -> None:
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


_configure_chinese_font()


SEMANTICS = {key: value for key, value in SEMANTIC_DEFINITIONS.items() if value.get("idx") is not None}


def create_app(workspace: str | Path | None = None) -> Flask:
    root = Path(workspace or Path.cwd())
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["WORKSPACE"] = root

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        tif, preview = _find_example_tif(root)
        shape = _load_ct_shape(root)
        raster_extent = _load_raster_extent(tif) if tif else None
        buoys = _load_buoy_points(root)
        return jsonify(
            {
                "tif": str(tif) if tif else None,
                "shape": shape,
                "raster": {"bbox": raster_extent} if raster_extent else None,
                "buoys": buoys,
                "preview": "/api/map-image",
                "semantics": [
                    {"id": key, "label": value["label"], "variable": value["variable"]}
                    for key, value in SEMANTICS.items()
                ],
            }
        )

    @app.get("/api/map-image")
    def map_image():
        tif, preview = _find_example_tif(root)
        if preview and preview.exists():
            return send_file(preview)
        image = _synthetic_map_png()
        return send_file(image, mimetype="image/png")

    @app.post("/api/query-point")
    def api_query_point():
        payload = request.get_json(force=True)
        semantic = str(payload.get("semantic", "hypoxia_layer"))
        x = float(payload.get("x", 0.5))
        y = float(payload.get("y", 0.5))
        shape = _load_ct_shape(root)
        if shape and not _point_in_shape(x, y, shape["rings"]):
            return jsonify({"error": "Selected point is outside the Changtan reservoir polygon."}), 400
        buoy = _sample_buoy_profile(root, x, y)
        remote = _sample_remote_sensing(root, x, y, shape)
        profile = _odc_point_profile(root, semantic, x, y) or _real_efdc_profile(root, semantic, x, y)
        fig = _point_figure(semantic, x, y, buoy, remote, profile)
        return jsonify(
            {
                "title": "Point multisource semantic query",
                "image": _fig_to_data_url(fig),
                "summary": _point_summary(semantic, x, y, buoy, remote, profile),
            }
        )

    @app.post("/api/query-region")
    def api_query_region():
        payload = request.get_json(force=True)
        semantic = str(payload.get("semantic", "hypoxia_layer"))
        box = payload.get("box", {})
        shape = _load_ct_shape(root)
        if shape:
            cx = (float(box.get("min_x", 0.0)) + float(box.get("max_x", 0.0))) / 2.0
            cy = (float(box.get("min_y", 0.0)) + float(box.get("max_y", 0.0))) / 2.0
            if not _point_in_shape(cx, cy, shape["rings"]):
                return jsonify({"error": "Selected region center is outside the Changtan reservoir polygon."}), 400
        odc_region = _odc_region_query(root, semantic, box)
        if odc_region:
            fig = _region_figure_from_panels(semantic, odc_region.get("panels", []), "Semantic Zarr via ODC")
            return jsonify(
                {
                    "title": "Regional semantic depth",
                    "image": _fig_to_data_url(fig),
                    "summary": _region_summary(semantic, box, odc_region),
                }
            )
        fig = _region_figure(semantic, box)
        return jsonify({"title": "Regional semantic depth", "image": _fig_to_data_url(fig), "summary": _region_summary(semantic, box)})

    return app


def _load_ct_shape(root: Path) -> dict | None:
    shp_paths = sorted((root / "ctshp").glob("*.shp"))
    if not shp_paths:
        return None
    try:
        rings, bbox = _read_polygon_shp(shp_paths[0])
    except Exception:
        return None
    if _shape_uses_utm_51n(shp_paths[0]):
        rings = [[list(_utm51n_to_lonlat(x, y)) for x, y in ring] for ring in rings]
        xs = [point[0] for ring in rings for point in ring]
        ys = [point[1] for ring in rings for point in ring]
        bbox = (min(xs), min(ys), max(xs), max(ys))
    return {
        "path": str(shp_paths[0]),
        "crs": "EPSG:4326",
        "bbox": {"min_x": bbox[0], "min_y": bbox[1], "max_x": bbox[2], "max_y": bbox[3]},
        "rings": rings,
    }


def _shape_uses_utm_51n(path: Path) -> bool:
    prj = path.with_suffix(".prj")
    if not prj.exists():
        return False
    text = prj.read_text(encoding="utf-8", errors="ignore")
    return "UTM_Zone_51N" in text or "Central_Meridian\",123" in text


def _utm51n_to_lonlat(easting: float, northing: float) -> tuple[float, float]:
    """Inverse WGS84 UTM Zone 51N transform, avoiding a runtime GIS dependency."""
    a = 6378137.0
    ecc_sq = 0.0066943799901413165
    k0 = 0.9996
    ecc_prime_sq = ecc_sq / (1 - ecc_sq)
    x = easting - 500000.0
    y = northing
    lon_origin = np.deg2rad(123.0)
    m = y / k0
    mu = m / (a * (1 - ecc_sq / 4 - 3 * ecc_sq**2 / 64 - 5 * ecc_sq**3 / 256))
    e1 = (1 - np.sqrt(1 - ecc_sq)) / (1 + np.sqrt(1 - ecc_sq))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * np.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * np.sin(4 * mu)
        + (151 * e1**3 / 96) * np.sin(6 * mu)
        + (1097 * e1**4 / 512) * np.sin(8 * mu)
    )
    n1 = a / np.sqrt(1 - ecc_sq * np.sin(phi1) ** 2)
    t1 = np.tan(phi1) ** 2
    c1 = ecc_prime_sq * np.cos(phi1) ** 2
    r1 = a * (1 - ecc_sq) / (1 - ecc_sq * np.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * np.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ecc_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ecc_prime_sq - 3 * c1**2) * d**6 / 720
    )
    lon = lon_origin + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ecc_prime_sq + 24 * t1**2) * d**5 / 120
    ) / np.cos(phi1)
    return float(np.rad2deg(lon)), float(np.rad2deg(lat))


def _load_raster_extent(tif: Path | None) -> dict | None:
    if not tif or not tif.exists():
        return None
    try:
        with tifffile.TiffFile(str(tif)) as dataset:
            page = dataset.pages[0]
            scale_tag = page.tags.get("ModelPixelScaleTag")
            tie_tag = page.tags.get("ModelTiepointTag")
            if not scale_tag or not tie_tag:
                return None
            scale_x, scale_y, _scale_z = scale_tag.value
            _px, _py, _pz, origin_x, origin_y, _oz = tie_tag.value[:6]
            height, width = page.shape[:2]
    except Exception:
        return None
    return {
        "min_x": float(origin_x),
        "max_x": float(origin_x + width * scale_x),
        "min_y": float(origin_y - height * scale_y),
        "max_y": float(origin_y),
    }


def _load_buoy_points(root: Path) -> list[dict]:
    path = root / "changtan_profile_buoy_point.xlsx"
    if not path.exists():
        return []
    try:
        df = pd.read_excel(path)
    except Exception:
        return []
    buoys = []
    for _, row in df.iterrows():
        try:
            lon = float(row["longitude"])
            lat = float(row["latitude"])
        except Exception:
            continue
        buoys.append(
            {
                "name": str(row.get("name", "") or row.get("stcd", "")),
                "stcd": str(row.get("stcd", "")),
                "longitude": lon,
                "latitude": lat,
            }
        )
    return buoys


def _read_polygon_shp(path: Path) -> tuple[list[list[list[float]]], tuple[float, float, float, float]]:
    """Read Polygon/PolygonZ rings from a shapefile without external GIS dependencies."""
    data = path.read_bytes()
    if len(data) < 100:
        raise ValueError("Invalid shapefile")
    bbox = struct.unpack("<4d", data[36:68])
    rings: list[list[list[float]]] = []
    offset = 100
    while offset + 8 <= len(data):
        _record_no, content_words = struct.unpack(">2i", data[offset : offset + 8])
        offset += 8
        content_bytes = content_words * 2
        record = data[offset : offset + content_bytes]
        offset += content_bytes
        if len(record) < 44:
            continue
        shape_type = struct.unpack("<i", record[:4])[0]
        if shape_type == 0:
            continue
        if shape_type not in {5, 15, 25}:
            continue
        num_parts, num_points = struct.unpack("<2i", record[36:44])
        parts_start = 44
        points_start = parts_start + num_parts * 4
        parts = list(struct.unpack(f"<{num_parts}i", record[parts_start:points_start]))
        points = [
            list(struct.unpack("<2d", record[points_start + i * 16 : points_start + (i + 1) * 16]))
            for i in range(num_points)
        ]
        parts.append(num_points)
        for start, end in zip(parts[:-1], parts[1:]):
            ring = points[start:end]
            if len(ring) >= 3:
                rings.append(ring)
    if not rings:
        raise ValueError("No polygon rings found")
    return rings, (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))


def _point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_shape(x: float, y: float, rings: list[list[list[float]]]) -> bool:
    return any(_point_in_ring(x, y, ring) for ring in rings)


def _find_example_tif(root: Path) -> tuple[Path | None, Path | None]:
    tif_root = root / "tif" / "S02093_Changtan"
    if not tif_root.exists():
        return None, None
    preferred_scene = tif_root / "20251006_20251006" / "S2_MSI_20251006022529_S02093_r0010_RGB.tif"
    preferred = [preferred_scene] if preferred_scene.exists() else sorted(tif_root.glob("**/*_RGB.tif"), reverse=True)
    tifs = preferred or sorted(tif_root.glob("**/*.tif"), reverse=True)
    if not tifs:
        return None, None
    tif = tifs[0]
    png = tif.with_suffix(".png")
    if png.exists():
        return tif, png
    siblings = sorted(tif.parent.glob("*.png"))
    return tif, siblings[0] if siblings else None


def _synthetic_map_png() -> io.BytesIO:
    yy, xx = np.mgrid[0:200, 0:120]
    lake = np.exp(-((xx - 60) ** 2 / 700 + (yy - 100) ** 2 / 4500))
    lake += 0.45 * np.exp(-((xx - 80) ** 2 / 160 + (yy - 45) ** 2 / 800))
    image = np.where(lake > 0.18, lake, np.nan)
    fig, ax = plt.subplots(figsize=(4, 6), dpi=140)
    ax.imshow(image, cmap="turbo", origin="upper")
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    return _fig_to_buffer(fig)


def _semantic_profile(semantic: str, x: float, y: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = np.arange(0, 169)
    depth = np.linspace(0, 17, 46)
    phase = 0.8 * np.sin((x + y) * np.pi)
    tt, zz = np.meshgrid(t, depth)
    if semantic == "hypoxia_layer":
        field = 10 - 0.42 * zz - 3.2 / (1 + np.exp(-(tt - 45) / 15)) + phase
        top = np.clip(6 + 0.06 * t - 2.2 * np.sin(t / 30 + x), 0, 16)
        bottom = np.minimum(17, top + 4 + 2 * np.sin(t / 50 + y))
    elif semantic == "algal_maximum_layer":
        field = 12 + 20 * np.exp(-((zz - (2 + 4 * np.sin(tt / 55 + x))) ** 2) / 8) + 4 * np.cos(tt / 30)
        top = np.clip(1.0 + 4.5 * np.sin(t / 60 + x), 0, 14)
        bottom = np.clip(top + 2.0 + np.sin(t / 18), top + 0.8, 17)
    elif semantic == "ammonium_enriched_layer":
        field = 0.08 + 0.028 * zz + 0.12 * np.sin(tt / 45 + y)
        top = np.clip(7 + 0.04 * t + 2 * np.sin(t / 25), 0, 16)
        bottom = np.minimum(17, top + 3.5)
    else:
        field = 25 - 0.65 * zz - 4 * np.tanh((zz - (4 + 0.05 * tt)) / 1.5)
        top = np.clip(2 + 0.08 * t, 0, 16)
        bottom = np.minimum(17, top + 1.8)
    return t, depth, field, top, bottom


def _point_figure(semantic: str, x: float, y: float, buoy: dict | None = None, remote: dict | None = None, profile: dict | None = None):
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    profile = profile or _real_efdc_profile(Path(current_app_config_root()), semantic, x, y)
    t = profile["hours"]
    depth = profile["depth"]
    field = profile["matrix"]
    boundary = profile["boundary"]
    top = boundary["z_top"].to_numpy(dtype="float64")
    bottom = boundary["z_bottom"].to_numpy(dtype="float64")
    fig, (ax, ax_profile) = plt.subplots(1, 2, figsize=(10.2, 4.8), dpi=140, gridspec_kw={"width_ratios": [3.1, 1.05]})
    im = ax.imshow(
        _scaled_for_display(field, meta),
        aspect="auto",
        origin="upper",
        extent=[t.min(), t.max(), depth.max(), depth.min()],
        cmap=meta["cmap"],
        vmin=meta["vmin"],
        vmax=meta["vmax"] or float(np.nanpercentile(_scaled_for_display(field, meta), 95)),
    )
    ax.plot(t, top, color="red", lw=1.8, label=meta.get("upper_label", "Semantic layer upper boundary"))
    ax.plot(t, bottom, color="black", lw=1.4, ls="--", label=meta.get("lower_label", "Semantic layer lower boundary"))
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Depth (m)")
    source_label = profile.get("catalog_mode", "Local fallback")
    ax.set_title(f"{meta['label']} from {source_label}\nModel hours {int(t.min())}-{int(t.max())}")
    ax.legend(loc="upper right", fontsize=7)
    cbar = fig.colorbar(im, ax=ax, pad=0.015)
    cbar.set_label(f"{meta['variable']} display scale ({meta['unit']})")

    if buoy and buoy.get("profile_depths") and buoy.get("profile_values"):
        ax_profile.plot(buoy["profile_values"], buoy["profile_depths"], color="#0b7f8c", marker="o", ms=2.5, lw=1.4)
        ax_profile.invert_yaxis()
        ax_profile.set_xlabel("Buoy profile")
        ax_profile.set_ylabel("Depth index")
    else:
        ax_profile.text(0.5, 0.5, "No buoy profile", ha="center", va="center", transform=ax_profile.transAxes)
        ax_profile.set_xticks([])
        ax_profile.set_yticks([])
    ax_profile.set_title("Profile buoy")
    if remote:
        label = []
        for key in ["Chla", "SDD", "Bloom"]:
            if key in remote:
                label.append(f"{key}: {remote[key]['value']}")
        ax_profile.text(
            0.02,
            0.02,
            "\n".join(label),
            transform=ax_profile.transAxes,
            fontsize=7,
            va="bottom",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#d7dee2"},
        )
    fig.tight_layout()
    return fig


def _scaled_for_display(values: np.ndarray, meta: dict) -> np.ndarray:
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


def _region_figure(semantic: str, box: dict):
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    panels = _real_region_panels(Path(current_app_config_root()), semantic, box)
    return _region_figure_from_panels(semantic, panels, "real EFDC TIF")


def _region_figure_from_panels(semantic: str, panels: list[dict], source_label: str):
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    rows, cols = 4, 7
    fig, axes = plt.subplots(rows, cols, figsize=(8, 7.6), dpi=130)
    im = None
    for i, ax in enumerate(axes.flat):
        if i >= len(panels):
            ax.set_axis_off()
            continue
        panel = panels[i]
        im = ax.imshow(np.array(panel["thickness"], dtype="float64"), cmap="turbo", vmin=0, vmax=30)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"h{panel['hour']:04d}", fontsize=7)
    fig.suptitle(f"{meta['label']} thickness - {source_label}", fontsize=12)
    fig.subplots_adjust(right=0.88, wspace=0.05, hspace=0.16)
    if im is not None:
        cax = fig.add_axes([0.9, 0.18, 0.025, 0.62])
        cbar = fig.colorbar(im, cax=cax)
        cbar.set_label("Thickness (m)")
    return fig


def _point_summary(
    semantic: str,
    x: float,
    y: float,
    buoy: dict | None = None,
    remote: dict | None = None,
    profile: dict | None = None,
) -> dict:
    root = Path(current_app_config_root())
    profile = profile or _real_efdc_profile(root, semantic, x, y)
    t = profile["hours"]
    boundary = profile["boundary"]
    top = boundary["z_top"].to_numpy(dtype="float64")
    bottom = boundary["z_bottom"].to_numpy(dtype="float64")
    occurrence = boundary["occurrence"].to_numpy(dtype="int8")
    summary = {
        "catalog_mode": profile.get("catalog_mode", "Local fallback"),
        "base_source": _display_semantic_source(root, str(profile.get("source", ""))),
        "semantic_source": _display_semantic_source(root, str(profile["semantic_source"])),
        "odc_semantic_dataset": profile.get("semantic_dataset", ""),
        "odc_base_dataset": profile.get("base_dataset", ""),
        "time_basis": "model_hour",
        "semantic": semantic,
        "rule": profile["rule"],
        "x": round(x, 6),
        "y": round(y, 6),
        "time_steps": int(len(t)),
        "occurrence_hours": int(np.nansum(occurrence)),
        "mean_top_depth_m": _round_or_blank(np.nanmean(top), 2),
        "mean_bottom_depth_m": _round_or_blank(np.nanmean(bottom), 2),
        "mean_thickness_m": _round_or_blank(np.nanmean(bottom - top), 2),
    }
    if buoy:
        summary.update(
            {
                "buoy_station": buoy.get("station", ""),
                "buoy_source_time": buoy.get("source_time", ""),
                "buoy_wt": buoy.get("wt", ""),
                "buoy_ph": buoy.get("ph", ""),
                "buoy_dox": buoy.get("dox", ""),
                "buoy_chla": buoy.get("chla", ""),
            }
        )
    if remote:
        summary.update(
            {
                "remote_scene_time": remote.get("scene_time", ""),
                "remote_chla": remote.get("Chla", {}).get("value", ""),
                "remote_sdd": remote.get("SDD", {}).get("value", ""),
                "remote_bloom": remote.get("Bloom", {}).get("value", ""),
            }
        )
    return summary


def _conda_python() -> Path | None:
    configured = os.environ.get("LAKE_SEMANTIC_PYTHON")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path(sys.executable))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _odc_query(root: Path, args: list[str], timeout: int = 120) -> dict | None:
    if os.environ.get("LAKE_SEMANTIC_CATALOG", "odc").lower() == "local":
        return None
    python_exe = _conda_python()
    script = root / "scripts" / "query_real_odc.py"
    if not python_exe or not script.exists():
        return None
    try:
        completed = subprocess.run(
            [str(python_exe), os.path.relpath(script, root), "--root", ".", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(root),
            timeout=timeout,
        )
        return json.loads(completed.stdout)
    except Exception as exc:
        try:
            error_path = root / "real_output" / "odc_query_error.log"
            error_path.parent.mkdir(parents=True, exist_ok=True)
            details = [f"{type(exc).__name__}: {exc}"]
            if hasattr(exc, "stderr") and exc.stderr:
                details.append(str(exc.stderr)[-4000:])
            if hasattr(exc, "stdout") and exc.stdout:
                details.append(str(exc.stdout)[-4000:])
            error_path.write_text("\n".join(details), encoding="utf-8")
        except Exception:
            pass
        return None


def _odc_point_profile(root: Path, semantic: str, x: float, y: float) -> dict | None:
    payload = _odc_query(
        root,
        ["--mode", "point", "--semantic", semantic, "--x", str(x), "--y", str(y)],
        timeout=120,
    )
    if not payload:
        return None
    boundary_payload = payload.get("boundary", {})
    boundary = pd.DataFrame(boundary_payload)
    return {
        "catalog_mode": payload.get("catalog_mode", "Open Data Cube"),
        "semantic_dataset": payload.get("semantic_dataset", ""),
        "base_dataset": payload.get("base_dataset", ""),
        "source": payload.get("base_source", ""),
        "semantic_source": payload.get("semantic_source", ""),
        "hours": np.array(payload["hours"], dtype="int64"),
        "depth": np.array(payload["depth"], dtype="float64"),
        "matrix": np.array(payload["matrix"], dtype="float64"),
        "boundary": boundary,
        "rule": payload.get("rule", ""),
        "query_rows": payload.get("query_rows", []),
    }


def _display_semantic_source(root: Path, source: str) -> str:
    if not source:
        return ""
    path_text, sep, bridge = source.partition(" via ")
    try:
        path_label = Path(path_text).resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        path_label = Path(path_text).name or path_text
    if sep:
        return f"{path_label} via configured conda Python"
    return path_label


def current_app_config_root() -> str:
    from flask import current_app

    return str(current_app.config["WORKSPACE"])


def _real_efdc_profile(root: Path, semantic: str, x: float, y: float) -> dict:
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    efdc_root = default_efdc_root(root)
    tif_dir = efdc_root / "hourtif"
    idx = int(meta["idx"])
    df = read_point_timeseries(tif_dir, x=x, y=y, idx=idx, start_hour=1, end_hour=169)
    if df.empty:
        raise ValueError(f"No EFDC TIF values found for idx={idx} at selected point")
    layers = sorted(LAYER_DEPTH_MAP)
    hours = sorted(df["hour"].unique())
    matrix = np.full((len(layers), len(hours)), np.nan, dtype="float64")
    hour_index = {hour: i for i, hour in enumerate(hours)}
    layer_index = {layer: i for i, layer in enumerate(layers)}
    for _, row in df.iterrows():
        matrix[layer_index[int(row["layer"])], hour_index[int(row["hour"])]] = float(row["value"])
    boundary, semantic_source = _semantic_boundary_from_real_zarr(root, semantic, x, y)
    if boundary.empty:
        boundary = semantic_boundary_timeseries(
            df,
            LAYER_DEPTH_MAP,
            threshold=float(meta["threshold"]),
            operator=str(meta["operator"]),
        )
        semantic_source = "runtime_from_real_efdc_tif"
    return {
        "source": tif_dir,
        "semantic_source": semantic_source,
        "hours": np.array(hours),
        "depth": np.array([LAYER_DEPTH_MAP[layer] for layer in layers], dtype="float64"),
        "matrix": matrix,
        "boundary": boundary,
        "rule": f"{meta['variable']} {meta['operator']} {meta['threshold']}",
    }


def _semantic_boundary_from_real_zarr(root: Path, semantic: str, x: float, y: float) -> tuple[pd.DataFrame, str]:
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    zarr_value = meta.get("semantic_zarr")
    if not zarr_value:
        return pd.DataFrame(), ""
    zarr_path = root / str(zarr_value)
    if not zarr_path.exists():
        return pd.DataFrame(), ""
    try:
        ds = open_zarr_like(zarr_path)
        point = ds.sel(x=x, y=y, method="nearest")
        df = pd.DataFrame(
            {
                "hour": np.arange(1, point.sizes["time"] + 1),
                "occurrence": point["occurrence"].to_numpy().astype("int8"),
                "z_top": point["z_top"].to_numpy(dtype="float64"),
                "z_bottom": point["z_bottom"].to_numpy(dtype="float64"),
                "thickness": point["thickness"].to_numpy(dtype="float64"),
                "layer_start": point["layer_start"].to_numpy(dtype="int16"),
                "layer_end": point["layer_end"].to_numpy(dtype="int16"),
            }
        )
        return df, str(zarr_path)
    except Exception:
        return _semantic_boundary_from_zarr_subprocess(root, zarr_path, x, y)


def _semantic_boundary_from_zarr_subprocess(root: Path, zarr_path: Path, x: float, y: float) -> tuple[pd.DataFrame, str]:
    configured = os.environ.get("LAKE_SEMANTIC_PYTHON")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path(sys.executable))
    script = root / "scripts" / "query_semantic_zarr_point.py"
    script_arg = os.path.relpath(script, root)
    zarr_arg = os.path.relpath(zarr_path, root)
    errors = []
    for python_exe in candidates:
        if not python_exe.exists() or not script.exists():
            continue
        try:
            completed = subprocess.run(
                [
                    str(python_exe),
                    script_arg,
                    "--zarr",
                    zarr_arg,
                    "--x",
                    str(x),
                    "--y",
                    str(y),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(root),
                timeout=30,
            )
            payload = json.loads(completed.stdout)
            return pd.DataFrame(payload), f"{zarr_path} via {python_exe}"
        except Exception as exc:
            errors.append(f"{python_exe}: {type(exc).__name__}: {exc}")
            if hasattr(exc, "stderr") and exc.stderr:
                errors.append(str(exc.stderr)[-1000:])
            continue
    try:
        error_path = root / "real_output" / "zarr_bridge_error.log"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text("\n".join(errors), encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame(), ""


def _odc_region_query(root: Path, semantic: str, box: dict) -> dict | None:
    payload = _odc_query(
        root,
        [
            "--mode",
            "region",
            "--semantic",
            semantic,
            "--min-x",
            str(float(box.get("min_x", 0.0))),
            "--min-y",
            str(float(box.get("min_y", 0.0))),
            "--max-x",
            str(float(box.get("max_x", 0.0))),
            "--max-y",
            str(float(box.get("max_y", 0.0))),
        ],
        timeout=180,
    )
    return payload


def _region_summary(semantic: str, box: dict, odc_region: dict | None = None) -> dict:
    if odc_region:
        stats = odc_region.get("stats") or []
        row = stats[0] if stats else {}
        return {
            "semantic": semantic,
            "box": box,
            "catalog_mode": odc_region.get("catalog_mode", "Open Data Cube"),
            "semantic_source": _display_semantic_source(Path(current_app_config_root()), str(odc_region.get("semantic_source", ""))),
            "base_source": _display_semantic_source(Path(current_app_config_root()), str(odc_region.get("base_source", ""))),
            "odc_semantic_dataset": odc_region.get("semantic_dataset", ""),
            "odc_base_dataset": odc_region.get("base_dataset", ""),
            "time_panels": 28,
            "time_steps": odc_region.get("time_steps", ""),
            "mean_value_in_semantic_layer": _round_or_blank(row.get("mean"), 3),
            "max_value_in_semantic_layer": _round_or_blank(row.get("max"), 3),
            "output": "Semantic Zarr thickness small multiples via Open Data Cube",
        }
    panels = _real_region_panels(Path(current_app_config_root()), semantic, box)
    arrays = [panel["thickness"][np.isfinite(panel["thickness"])].ravel() for panel in panels]
    values = np.concatenate(arrays) if arrays else np.array([])
    return {
        "semantic": semantic,
        "box": box,
        "time_panels": len(panels),
        "source": "efdc_hour/hourtif",
        "mean_thickness_m": _round_or_blank(np.nanmean(values), 2) if values.size else "",
        "max_thickness_m": _round_or_blank(np.nanmax(values), 2) if values.size else "",
        "output": "real EFDC semantic thickness small multiples",
    }


def _real_region_panels(root: Path, semantic: str, box: dict) -> list[dict]:
    meta = SEMANTICS.get(semantic, SEMANTICS["hypoxia_layer"])
    tif_dir = default_efdc_root(root) / "hourtif"
    idx = int(meta["idx"])
    records = [item for item in scan_efdc_tifs(tif_dir) if item.idx == idx]
    if not records:
        return []
    grid = raster_grid(records[0].path)
    r1, c1 = grid.row_col(float(box.get("min_x", grid.min_x)), float(box.get("max_y", grid.max_y)))
    r2, c2 = grid.row_col(float(box.get("max_x", grid.max_x)), float(box.get("min_y", grid.min_y)))
    row_slice = slice(max(0, min(r1, r2)), min(grid.height, max(r1, r2) + 1))
    col_slice = slice(max(0, min(c1, c2)), min(grid.width, max(c1, c2) + 1))
    if row_slice.stop - row_slice.start < 4 or col_slice.stop - col_slice.start < 4:
        row_slice = slice(0, grid.height)
        col_slice = slice(0, grid.width)
    selected_hours = np.linspace(1, 169, 28, dtype=int)
    by_hour_layer = {(item.hour, item.layer): item.path for item in records}
    panels = []
    for hour in selected_hours:
        stack = []
        for layer in sorted(LAYER_DEPTH_MAP):
            path = by_hour_layer.get((int(hour), layer))
            if not path:
                stack.append(np.full((row_slice.stop - row_slice.start, col_slice.stop - col_slice.start), np.nan))
                continue
            arr = tifffile.imread(str(path)).astype("float64")[row_slice, col_slice]
            arr[arr == -999.0] = np.nan
            stack.append(arr)
        values = np.stack(stack, axis=0)
        if meta["operator"] == "<":
            mask = values < float(meta["threshold"])
        elif meta["operator"] == ">":
            mask = values > float(meta["threshold"])
        elif meta["operator"] == "<=":
            mask = values <= float(meta["threshold"])
        else:
            mask = values >= float(meta["threshold"])
        thickness = _semantic_thickness_from_mask(mask)
        panels.append({"hour": int(hour), "thickness": thickness})
    return panels


def _semantic_thickness_from_mask(mask: np.ndarray) -> np.ndarray:
    depths = np.array([LAYER_DEPTH_MAP[layer] for layer in sorted(LAYER_DEPTH_MAP)], dtype="float64")
    out = np.full(mask.shape[1:], np.nan, dtype="float32")
    for row in range(mask.shape[1]):
        for col in range(mask.shape[2]):
            valid = np.where(np.nan_to_num(mask[:, row, col], nan=False))[0]
            if valid.size == 0:
                out[row, col] = 0.0
                continue
            splits = np.where(np.diff(valid) > 1)[0] + 1
            segment = max(np.split(valid, splits), key=len)
            out[row, col] = float(np.nanmax(depths[segment]) - np.nanmin(depths[segment]))
    return out


def _sample_buoy_profile(root: Path, x: float, y: float) -> dict | None:
    path = root / "剖面浮标.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["spt_parsed"] = pd.to_datetime(df.get("spt"), errors="coerce")
    value_cols = ["wt", "ph", "dox", "turb", "cond", "chla", "nh3n", "water_level"]
    for col in value_cols:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    usable = df.dropna(subset=[col for col in ["wt", "ph", "dox"] if col in df], how="all").reset_index(drop=True)
    if usable.empty:
        return None
    selector = abs(np.sin((x * 12.9898 + y * 78.233) * 43758.5453))
    row = usable.iloc[int(selector * (len(usable) - 1))]
    profile_cols = [col for col in df.columns if re.fullmatch(r"x010\d{2}", col)]
    profile_values = pd.to_numeric(row[profile_cols], errors="coerce").to_numpy(dtype="float64") if profile_cols else np.array([])
    valid = np.isfinite(profile_values)
    return {
        "station": str(row.get("stcd", "")),
        "source_time": str(row.get("spt", "")),
        "wt": _round_or_blank(row.get("wt")),
        "ph": _round_or_blank(row.get("ph")),
        "dox": _round_or_blank(row.get("dox")),
        "chla": _round_or_blank(row.get("chla")),
        "profile_depths": np.arange(1, len(profile_values) + 1, dtype="float64")[valid].tolist(),
        "profile_values": profile_values[valid].round(3).tolist(),
    }


def _sample_remote_sensing(root: Path, x: float, y: float, shape: dict | None) -> dict:
    tif, _preview = _find_example_tif(root)
    scene_dir = tif.parent if tif else root / "tif" / "S02093_Changtan" / "20251006_20251006"
    scene_time = _scene_time_from_path(scene_dir)
    result: dict[str, dict] = {"scene_time": scene_time}
    raster_extent = _load_raster_extent(tif) if tif else None
    raster_shape = {"bbox": raster_extent} if raster_extent else shape
    for name in ["Chla", "SDD", "Bloom"]:
        paths = sorted(scene_dir.glob(f"*_{name}.tif"))
        if not paths:
            continue
        try:
            arr = tifffile.imread(str(paths[0])).astype("float64")
            row, col = _map_to_array_index(x, y, arr.shape, raster_shape)
            value = _window_value(arr, row, col)
            result[name] = {"value": _round_or_blank(value), "path": str(paths[0])}
        except Exception as exc:
            result[name] = {"value": f"unreadable: {exc}", "path": str(paths[0])}
    return result


def _map_to_array_index(x: float, y: float, shape: tuple[int, int], lake_shape: dict | None) -> tuple[int, int]:
    height, width = shape[:2]
    if lake_shape:
        bbox = lake_shape["bbox"]
        nx = (x - bbox["min_x"]) / ((bbox["max_x"] - bbox["min_x"]) or 1.0)
        ny = (bbox["max_y"] - y) / ((bbox["max_y"] - bbox["min_y"]) or 1.0)
    else:
        nx, ny = x, 1.0 - y
    row = int(np.clip(round(ny * (height - 1)), 0, height - 1))
    col = int(np.clip(round(nx * (width - 1)), 0, width - 1))
    return row, col


def _window_value(arr: np.ndarray, row: int, col: int) -> float:
    for radius in [2, 5, 10, 20]:
        r0, r1 = max(0, row - radius), min(arr.shape[0], row + radius + 1)
        c0, c1 = max(0, col - radius), min(arr.shape[1], col + radius + 1)
        window = arr[r0:r1, c0:c1]
        valid = window[np.isfinite(window) & (window != 0)]
        if valid.size:
            return float(np.nanmedian(valid))
    return float(arr[row, col])


def _scene_time_from_path(path: Path) -> str:
    match = re.search(r"20\d{6}", str(path))
    if not match:
        return DEMO_TIME
    value = match.group(0)
    return f"{value[:4]}-{value[4:6]}-{value[6:8]} 02:40:09"


def _round_or_blank(value, ndigits: int = 3):
    try:
        if pd.isna(value):
            return ""
        return round(float(value), ndigits)
    except Exception:
        return ""


def _fig_to_buffer(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _fig_to_data_url(fig) -> str:
    buf = _fig_to_buffer(fig)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def run_ui(host: str = "127.0.0.1", port: int = 5050, workspace: str | Path | None = None) -> None:
    create_app(workspace).run(host=host, port=port, debug=False)
