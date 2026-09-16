from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


def _first_existing(columns: list[str], candidates: list[str]) -> str | None:
    lower = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


@dataclass(frozen=True)
class ProfileObservations:
    """Tabular point-profile observations with actual depth retained."""

    data: pd.DataFrame
    station_col: str
    time_col: str
    depth_col: str
    variable_cols: tuple[str, ...]
    lon_col: str | None = None
    lat_col: str | None = None

    def match_semantic_interval(self, z_top: float, z_bottom: float) -> pd.DataFrame:
        depth = pd.to_numeric(self.data[self.depth_col], errors="coerce")
        return self.data[(depth >= z_top) & (depth <= z_bottom)].copy()


@dataclass(frozen=True)
class ProfileAdapter:
    """Read CSV/XLS/XLSX profile observations without mapping them to model layers."""

    path: Path
    station_col: str | None = None
    time_col: str | None = None
    depth_col: str | None = None
    lon_col: str | None = None
    lat_col: str | None = None

    def read(self) -> ProfileObservations:
        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(self.path)
        elif suffix in {".xls", ".xlsx"}:
            df = pd.read_excel(self.path)
        else:
            raise ValueError(f"Unsupported profile table format: {self.path}")

        columns = list(df.columns)
        station = self.station_col or _first_existing(columns, ["station", "stcd", "site", "id"]) or columns[0]
        time = self.time_col or _first_existing(columns, ["time", "datetime", "date", "spt"])
        depth = self.depth_col or _first_existing(columns, ["actual_depth", "depth", "depth_m", "water_depth"])
        lon = self.lon_col or _first_existing(columns, ["longitude", "lon", "x", "coordinate1"])
        lat = self.lat_col or _first_existing(columns, ["latitude", "lat", "y", "coordinate2"])
        if time is None:
            raise ValueError("Profile observations require a time column")
        if depth is None:
            raise ValueError("Profile observations require an actual depth column")
        non_variables = {station, time, depth, lon, lat, None}
        variable_cols = tuple(col for col in columns if col not in non_variables and pd.api.types.is_numeric_dtype(df[col]))
        if not variable_cols:
            raise ValueError("No numeric profile variable columns found")
        df = df.copy()
        df[time] = pd.to_datetime(df[time], errors="coerce")
        df[depth] = pd.to_numeric(df[depth], errors="coerce")
        return ProfileObservations(df, station, time, depth, variable_cols, lon, lat)


def profile_depth_mask(depths: np.ndarray, z_top: float, z_bottom: float) -> np.ndarray:
    return (np.asarray(depths, dtype="float64") >= z_top) & (np.asarray(depths, dtype="float64") <= z_bottom)
