from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zarr", required=True)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    args = parser.parse_args()
    ds = xr.open_zarr(Path(args.zarr), consolidated=True)
    point = ds.sel(x=args.x, y=args.y, method="nearest")
    payload = {
        "hour": list(range(1, point.sizes["time"] + 1)),
        "occurrence": point["occurrence"].to_numpy().astype("int8").tolist(),
        "z_top": _clean(point["z_top"].to_numpy().astype("float64")),
        "z_bottom": _clean(point["z_bottom"].to_numpy().astype("float64")),
        "thickness": _clean(point["thickness"].to_numpy().astype("float64")),
        "layer_start": point["layer_start"].to_numpy().astype("int16").tolist(),
        "layer_end": point["layer_end"].to_numpy().astype("int16").tolist(),
    }
    print(json.dumps(payload))


def _clean(values: np.ndarray) -> list[float | None]:
    out = []
    for value in values:
        if pd.isna(value):
            out.append(None)
        else:
            out.append(float(value))
    return out


if __name__ == "__main__":
    main()
