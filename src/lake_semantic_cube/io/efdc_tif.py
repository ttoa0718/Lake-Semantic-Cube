from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile


FILENAME_RE = re.compile(r"WQ_TSK_(?P<layer>\d+)_DOM_(?P<hour>\d+)_(?P<idx>\d+)\.tif$", re.IGNORECASE)

VARIABLES = {
    1: {"name": "CHC", "label": "Chla / blue-green algae", "unit": "ug/L"},
    2: {"name": "CHG", "label": "diatoms", "unit": "1"},
    3: {"name": "CHD", "label": "green algae", "unit": "1"},
    14: {"name": "NHX", "label": "ammonium nitrogen", "unit": "mg/L"},
    18: {"name": "COD", "label": "COD", "unit": "mg/L"},
    19: {"name": "DOX", "label": "dissolved oxygen", "unit": "mg/L"},
}

LAYER_DEPTH_MAP = {
    1: 30.0,
    2: 27.0,
    3: 24.0,
    4: 21.0,
    5: 18.0,
    6: 15.0,
    7: 12.0,
    8: 9.0,
    9: 6.0,
    10: 3.0,
}

SEMANTIC_DEFINITIONS = {
    "hypoxia_layer": {
        "label": "Hypoxia layer",
        "variable": "DOX",
        "idx": 19,
        "threshold": 7.2,
        "operator": "<",
        "unit": "mg/L",
        "upper_label": "Hypoxia layer upper boundary",
        "lower_label": "Hypoxia layer lower boundary",
        "raw_min": 0.0,
        "raw_max": 9.0,
        "vmin": 0.0,
        "vmax": 12.0,
        "cmap": "turbo_r",
        "semantic_zarr": "real_output/semantic_hypoxia_dox_169h.zarr",
    },
    "ammonium_enriched_layer": {
        "label": "Ammonium-enriched layer",
        "variable": "NHX",
        "idx": 14,
        "threshold": 0.01,
        "operator": ">",
        "unit": "mg/L",
        "upper_label": "Ammonium-enriched layer upper boundary",
        "lower_label": "Ammonium-enriched layer lower boundary",
        "raw_min": 0.0,
        "raw_max": 0.04,
        "vmin": 0.0,
        "vmax": 0.3,
        "cmap": "turbo",
        "semantic_zarr": "real_output/semantic_ammonium_nhx_169h.zarr",
    },
    "cod_enriched_layer": {
        "label": "Organic matter-enriched layer",
        "variable": "CODmn",
        "idx": 18,
        "threshold": 8.0,
        "operator": ">",
        "unit": "mg/L",
        "upper_label": "Organic matter-enriched layer upper boundary",
        "lower_label": "Organic matter-enriched layer lower boundary",
        "raw_min": 0.0,
        "raw_max": 12.0,
        "vmin": 0.0,
        "vmax": 4.0,
        "cmap": "turbo",
        "semantic_zarr": "real_output/semantic_codmn_169h.zarr",
    },
    "cyanobacteria_enriched_layer": {
        "label": "Cyanobacteria-enriched layer",
        "variable": "Chla",
        "idx": 1,
        "threshold": 0.7,
        "operator": ">",
        "unit": "ug/L",
        "upper_label": "Cyanobacteria-enriched layer upper boundary",
        "lower_label": "Cyanobacteria-enriched layer lower boundary",
        "raw_min": 0.0,
        "raw_max": 2.0,
        "vmin": 0.0,
        "vmax": 80.0,
        "cmap": "turbo",
        "semantic_zarr": "real_output/semantic_cyanobacteria_chla_169h.zarr",
    },
}


@dataclass(frozen=True)
class EFDCTifRecord:
    path: Path
    layer: int
    hour: int
    idx: int


@dataclass(frozen=True)
class RasterGrid:
    width: int
    height: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def row_col(self, x: float, y: float) -> tuple[int, int]:
        col = int(np.clip(round((x - self.min_x) / ((self.max_x - self.min_x) or 1.0) * (self.width - 1)), 0, self.width - 1))
        row = int(np.clip(round((self.max_y - y) / ((self.max_y - self.min_y) or 1.0) * (self.height - 1)), 0, self.height - 1))
        return row, col


def default_efdc_root(workspace: str | Path) -> Path:
    workspace = Path(workspace).resolve()
    candidates = [
        workspace / "efdc_hour",
        workspace.parent / "efdc_hour",
        workspace / "efdc_hour.lnk",
        workspace.parent / "efdc_hour.lnk",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.suffix.lower() == ".lnk":
            target = _resolve_windows_shortcut(candidate)
            if target and target.exists():
                return target
            continue
        return candidate
    return workspace / "efdc_hour"


def _resolve_windows_shortcut(path: Path) -> Path | None:
    if path.suffix.lower() != ".lnk":
        return path
    escaped = str(path).replace("'", "''")
    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{escaped}'); $s.TargetPath"
    )
    try:
        powershell = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        completed = subprocess.run(
            [
                str(powershell) if powershell.exists() else "powershell.exe",
                "-NoProfile",
                "-Command",
                command,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except Exception:
        return None
    target = completed.stdout.strip()
    return Path(target) if target else None


def scan_efdc_tifs(tif_dir: str | Path) -> list[EFDCTifRecord]:
    records = []
    for path in Path(tif_dir).glob("*.tif"):
        match = FILENAME_RE.match(path.name)
        if not match:
            continue
        records.append(
            EFDCTifRecord(
                path=path,
                layer=int(match.group("layer")),
                hour=int(match.group("hour")),
                idx=int(match.group("idx")),
            )
        )
    return sorted(records, key=lambda item: (item.idx, item.hour, item.layer))


def raster_grid(path: str | Path) -> RasterGrid:
    with tifffile.TiffFile(str(path)) as dataset:
        page = dataset.pages[0]
        height, width = page.shape[:2]
        scale = page.tags["ModelPixelScaleTag"].value
        tie = page.tags["ModelTiepointTag"].value
    scale_x, scale_y = float(scale[0]), float(scale[1])
    origin_x, origin_y = float(tie[3]), float(tie[4])
    return RasterGrid(
        width=width,
        height=height,
        min_x=origin_x,
        max_x=origin_x + width * scale_x,
        min_y=origin_y - height * scale_y,
        max_y=origin_y,
    )


def read_point_timeseries(
    tif_dir: str | Path,
    x: float,
    y: float,
    idx: int,
    start_hour: int | None = None,
    end_hour: int | None = None,
    nodata: float = -999.0,
) -> pd.DataFrame:
    records = [item for item in scan_efdc_tifs(tif_dir) if item.idx == idx]
    if not records:
        return pd.DataFrame(columns=["hour", "layer", "value"])
    grid = raster_grid(records[0].path)
    row, col = grid.row_col(x, y)
    rows = []
    for record in records:
        if start_hour is not None and record.hour < start_hour:
            continue
        if end_hour is not None and record.hour > end_hour:
            continue
        try:
            arr = tifffile.imread(str(record.path))
            value = float(arr[row, col])
        except Exception:
            continue
        if not np.isfinite(value) or value == nodata:
            continue
        rows.append({"hour": record.hour, "layer": record.layer, "idx": record.idx, "value": value, "row": row, "col": col})
    return pd.DataFrame(rows).sort_values(["hour", "layer"]).reset_index(drop=True)


def semantic_boundary_timeseries(
    df: pd.DataFrame,
    depth_by_layer: dict[int, float],
    threshold: float,
    operator: str,
) -> pd.DataFrame:
    layers = sorted(depth_by_layer)
    depths = np.array([depth_by_layer[layer] for layer in layers], dtype="float64")
    layer_index = {layer: i for i, layer in enumerate(layers)}
    rows = []
    for hour, group in df.groupby("hour"):
        profile = np.full(len(layers), np.nan, dtype="float64")
        for _, item in group.iterrows():
            layer = int(item["layer"])
            if layer in layer_index:
                profile[layer_index[layer]] = float(item["value"])
        if operator == "<":
            mask = profile < threshold
        elif operator == ">":
            mask = profile > threshold
        elif operator == "<=":
            mask = profile <= threshold
        elif operator == ">=":
            mask = profile >= threshold
        else:
            raise ValueError(f"Unsupported operator: {operator}")
        valid = np.where(np.nan_to_num(mask, nan=False))[0]
        if valid.size == 0:
            rows.append({"hour": int(hour), "occurrence": 0, "z_top": np.nan, "z_bottom": np.nan, "thickness": 0.0, "layer_start": -1, "layer_end": -1})
            continue
        splits = np.where(np.diff(valid) > 1)[0] + 1
        segments = np.split(valid, splits)
        segment = max(segments, key=len)
        top = float(np.nanmin(depths[segment]))
        bottom = float(np.nanmax(depths[segment]))
        rows.append(
            {
                "hour": int(hour),
                "occurrence": 1,
                "z_top": top,
                "z_bottom": bottom,
                "thickness": bottom - top,
                "layer_start": int(layers[int(segment.min())]),
                "layer_end": int(layers[int(segment.max())]),
            }
        )
    return pd.DataFrame(rows)
