from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

MODEL_TIF_PATTERN = re.compile(
    r"WQ_TSK_(?P<layer>\d+)_DOM_(?P<hour>\d+)_(?P<variable>\d+|[A-Za-z0-9]+)\.tif$",
    re.IGNORECASE,
)


def model_hour_to_datetime(start_time: datetime, model_hour: int, hour_base: int = 1) -> datetime:
    """Convert a model DOM/hour index to a datetime using one configured convention."""
    return start_time + timedelta(hours=int(model_hour) - int(hour_base))


def datetime_to_model_hour(start_time: datetime, value: datetime, hour_base: int = 1) -> int:
    """Convert datetime back to the configured model hour index."""
    delta_hours = int((value - start_time).total_seconds() // 3600)
    return delta_hours + int(hour_base)


def parse_model_tif_filename(path: str | Path) -> dict[str, int | str]:
    """Parse EFDC-style water-quality GeoTIFF names."""
    name = Path(path).name
    match = MODEL_TIF_PATTERN.match(name)
    if not match:
        raise ValueError(f"Not an EFDC model GeoTIFF name: {name}")
    variable_raw = match.group("variable")
    variable: int | str = int(variable_raw) if variable_raw.isdigit() else variable_raw
    return {
        "layer": int(match.group("layer")),
        "hour": int(match.group("hour")),
        "variable": variable,
    }
