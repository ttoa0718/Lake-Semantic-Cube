from __future__ import annotations

import pickle
from pathlib import Path

import xarray as xr


def has_zarr() -> bool:
    try:
        import zarr  # noqa: F401

        return True
    except Exception:
        return False


def write_zarr_like(ds: xr.Dataset, path: str | Path, encoding: dict | None = None) -> None:
    """Write real Zarr when available, otherwise a directory fallback for tests/demo."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if has_zarr():
        ds.to_zarr(target, mode="w", consolidated=True, encoding=encoding)
        return
    target.mkdir(parents=True, exist_ok=True)
    payload = target / "data.pkl"
    marker = target / ".lake_semantic_cube_fallback"
    with payload.open("wb") as f:
        pickle.dump(ds, f)
    marker.write_text("zarr package unavailable; xarray Dataset pickle fallback\n", encoding="utf-8")


def open_zarr_like(path: str | Path) -> xr.Dataset:
    """Open real Zarr or the local fallback written by write_zarr_like."""
    target = Path(path)
    payload = target / "data.pkl"
    if payload.exists():
        with payload.open("rb") as f:
            return pickle.load(f)
    return xr.open_zarr(target, consolidated=True)
