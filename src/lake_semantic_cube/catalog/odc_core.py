from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np
import xarray as xr
import yaml

from lake_semantic_cube.io.efdc_tif import SEMANTIC_DEFINITIONS, default_efdc_root
from lake_semantic_cube.io.storage import open_zarr_like

from .eo3 import deterministic_dataset_uuid
from .odc import DatasetRecord


SEMANTIC_MEASUREMENTS = {
    "occurrence": {"dtype": "uint8", "units": "1", "nodata": 0},
    "z_top": {"dtype": "float32", "units": "m", "nodata": "NaN"},
    "z_bottom": {"dtype": "float32", "units": "m", "nodata": "NaN"},
    "thickness": {"dtype": "float32", "units": "m", "nodata": "NaN"},
    "core_depth": {"dtype": "float32", "units": "m", "nodata": "NaN"},
    "segment_count": {"dtype": "int16", "units": "1", "nodata": -1},
    "layer_start": {"dtype": "int16", "units": "1", "nodata": -1},
    "layer_end": {"dtype": "int16", "units": "1", "nodata": -1},
    "semantic_mask": {"dtype": "uint8", "units": "1", "nodata": 0},
}

BASE_ZARR_PRODUCT = "changtan_base_zarr_real"
BASE_HOURTIF_PRODUCT = "changtan_efdc_hourtif_real"
SEMANTIC_PRODUCT = "changtan_vertical_semantic_real"

BASE_ZARR_MEASUREMENTS = {
    "Chla": {"dtype": "float32", "units": "ug/L", "nodata": "NaN"},
    "NHX": {"dtype": "float32", "units": "mg/L", "nodata": "NaN"},
    "CODmn": {"dtype": "float32", "units": "mg/L", "nodata": "NaN"},
    "DOX": {"dtype": "float32", "units": "mg/L", "nodata": "NaN"},
}


@dataclass(frozen=True)
class ODCCommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def default_datacube_exe() -> Path:
    configured = os.environ.get("DATACUBE_EXE")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path("datacube"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path("datacube")


def datacube_env() -> dict[str, str]:
    env = dict(os.environ)
    return env


class OpenDataCubeIndexer:
    """Thin adapter around the real Open Data Cube command-line index."""

    def __init__(self, datacube_exe: str | Path | None = None, cwd: str | Path | None = None):
        self.datacube_exe = Path(datacube_exe) if datacube_exe else default_datacube_exe()
        self.cwd = Path(cwd) if cwd else None

    def run(self, args: list[str], check: bool = False) -> ODCCommandResult:
        command = [str(self.datacube_exe), *args]
        completed = subprocess.run(
            command,
            cwd=str(self.cwd) if self.cwd else None,
            env=datacube_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )
        result = ODCCommandResult(command, completed.returncode, completed.stdout, completed.stderr)
        if check and not result.ok:
            raise RuntimeError(result.stderr or result.stdout or f"ODC command failed: {' '.join(command)}")
        return result

    def product_add(self, product_yaml: str | Path) -> ODCCommandResult:
        return self.run(["product", "add", str(product_yaml)])

    def dataset_add(self, dataset_yaml: str | Path) -> ODCCommandResult:
        return self.run(["dataset", "add", str(dataset_yaml)])

    def product_list(self) -> ODCCommandResult:
        return self.run(["product", "list"])

    def dataset_count(self, product: str) -> ODCCommandResult:
        return self.run(["dataset", "count", product])

    def dataset_search(self, product: str) -> ODCCommandResult:
        return self.run(["dataset", "search", f"product={product}"])


class OpenDataCubeDatasetCatalog:
    """Dataset search adapter backed by a real Open Data Cube index."""

    def __init__(self, datacube_exe: str | Path | None = None, cwd: str | Path | None = None):
        self.indexer = OpenDataCubeIndexer(datacube_exe=datacube_exe, cwd=cwd)

    def _search_product(self, product: str) -> list[dict[str, Any]]:
        result = self.indexer.dataset_search(product)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout)
        docs = [doc for doc in yaml.safe_load_all(result.stdout) if isinstance(doc, dict)]
        return docs

    @staticmethod
    def _path_from_location(location: str) -> str:
        parsed = urlparse(location)
        if parsed.scheme == "file":
            path = unquote(parsed.path)
            if len(path) >= 3 and path[0] == "/" and path[2] == ":":
                path = path[1:]
            return path
        return location

    @staticmethod
    def _semantic_type_from_doc(doc: dict[str, Any]) -> str | None:
        fields = doc.get("fields", {})
        label = str(fields.get("label", doc.get("label", "")))
        prefix = "changtan_vertical_semantic_real_"
        if label.startswith(prefix):
            return label[len(prefix) :]
        location = str(doc.get("location", ""))
        for semantic_type, definition in SEMANTIC_DEFINITIONS.items():
            if str(definition.get("semantic_zarr", "")).replace("\\", "/").split("/")[-1] in location:
                return semantic_type
        return None

    @staticmethod
    def _time_intersects(doc: dict[str, Any], time: tuple[str, str] | None) -> bool:
        if time is None:
            return True
        fields = doc.get("fields", {})
        doc_time = fields.get("time", {}) if isinstance(fields, dict) else {}
        if not isinstance(doc_time, dict):
            return True
        begin = doc_time.get("begin")
        end = doc_time.get("end")
        if not begin or not end:
            return True
        try:
            query_begin = _parse_time(time[0])
            query_end = _parse_time(time[1])
            doc_begin = _parse_time(str(begin))
            doc_end = _parse_time(str(end))
        except ValueError:
            return True
        return query_begin <= doc_end and query_end >= doc_begin

    @staticmethod
    def _space_intersects(doc: dict[str, Any], space: Any | None) -> bool:
        if space is None:
            return True
        geometry = doc.get("geometry", {})
        coordinates = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
        points = []
        for polygon in coordinates:
            for ring in polygon:
                points.extend(ring)
        if not points:
            return True
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if hasattr(space, "x") and hasattr(space, "y"):
            return min_x <= float(space.x) <= max_x and min_y <= float(space.y) <= max_y
        if all(hasattr(space, key) for key in ("min_x", "min_y", "max_x", "max_y")):
            return not (
                float(space.max_x) < min_x
                or float(space.min_x) > max_x
                or float(space.max_y) < min_y
                or float(space.min_y) > max_y
            )
        return True

    def find_semantic_datasets(
        self,
        semantic_type: str,
        product: str | None = None,
        time: tuple[str, str] | None = None,
        space: Any | None = None,
    ) -> list[DatasetRecord]:
        product_name = product or SEMANTIC_PRODUCT
        records = []
        for doc in self._search_product(product_name):
            if not self._time_intersects(doc, time) or not self._space_intersects(doc, space):
                continue
            found_type = self._semantic_type_from_doc(doc)
            if found_type != semantic_type:
                continue
            location = str(doc.get("location", ""))
            fields = doc.get("fields", {})
            measurements = fields.get("measurements", {})
            doc_time = fields.get("time", {})
            records.append(
                DatasetRecord(
                    id=str(doc.get("id")),
                    product=str(doc.get("product", product_name)),
                    uri=self._path_from_location(location),
                    data_type="semantic",
                    variables=list(measurements),
                    properties={"semantic:type": found_type, "odc:file_format": fields.get("format", "Zarr")},
                    time_start=str(doc_time.get("begin")) if isinstance(doc_time, dict) else None,
                    time_end=str(doc_time.get("end")) if isinstance(doc_time, dict) else None,
                )
            )
        return records

    def find_base_datasets(
        self,
        product: str | None = None,
        variables: list[str] | None = None,
        product_type: str | None = None,
        time: tuple[str, str] | None = None,
        space: Any | None = None,
    ) -> list[DatasetRecord]:
        product_name = product or BASE_ZARR_PRODUCT
        records = []
        for doc in self._search_product(product_name):
            if not self._time_intersects(doc, time) or not self._space_intersects(doc, space):
                continue
            fields = doc.get("fields", {})
            measurements = fields.get("measurements", {})
            doc_time = fields.get("time", {})
            file_format = str(fields.get("format", ""))
            records.append(
                DatasetRecord(
                    id=str(doc.get("id")),
                    product=str(doc.get("product", product_name)),
                    uri=self._path_from_location(str(doc.get("location", ""))),
                    data_type="model" if product_name == BASE_ZARR_PRODUCT else "model_tif_collection",
                    variables=list(measurements) or (variables or []),
                    properties={"odc:file_format": file_format},
                    time_start=str(doc_time.get("begin")) if isinstance(doc_time, dict) else None,
                    time_end=str(doc_time.get("end")) if isinstance(doc_time, dict) else None,
                )
            )
        if variables:
            records = [record for record in records if set(variables).issubset(set(record.variables))]
        if product_type:
            records = [record for record in records if record.data_type == product_type]
        return records


def file_uri(path: str | Path) -> str:
    return Path(path).resolve().as_uri()


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _time_text(ds: xr.Dataset, index: int) -> str:
    return np.datetime_as_string(ds.time.values[index], unit="s") + "Z"


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed


def _bbox_from_zarr(ds: xr.Dataset) -> tuple[float, float, float, float]:
    x = ds["x"].to_numpy().astype("float64")
    y = ds["y"].to_numpy().astype("float64")
    return float(np.nanmin(x)), float(np.nanmin(y)), float(np.nanmax(x)), float(np.nanmax(y))


def _grid_from_zarr(ds: xr.Dataset) -> dict[str, Any]:
    x = ds["x"].to_numpy().astype("float64")
    y = ds["y"].to_numpy().astype("float64")
    res_x = float(np.nanmedian(np.diff(x))) if x.size > 1 else 1.0
    res_y = float(np.nanmedian(np.diff(y))) if y.size > 1 else -1.0
    return {
        "shape": [int(ds.sizes["y"]), int(ds.sizes["x"])],
        "transform": [res_x, 0.0, float(x[0] - res_x / 2.0), 0.0, res_y, float(y[0] - res_y / 2.0)],
    }


def semantic_product_doc(product_name: str = SEMANTIC_PRODUCT) -> dict[str, Any]:
    return {
        "name": product_name,
        "description": "Changtan vertical semantic-layer products indexed by Open Data Cube",
        "metadata_type": "eo3",
        "metadata": {"product": {"name": product_name}},
        "measurements": [
            {"name": name, **definition}
            for name, definition in SEMANTIC_MEASUREMENTS.items()
        ],
    }


def base_hourtif_product_doc(product_name: str = BASE_HOURTIF_PRODUCT) -> dict[str, Any]:
    return {
        "name": product_name,
        "description": "Changtan EFDC hourly water-quality GeoTIFF collection",
        "metadata_type": "eo3",
        "metadata": {"product": {"name": product_name}},
        "measurements": [
            {"name": "value", "dtype": "float32", "units": "unknown", "nodata": "NaN"},
        ],
    }


def base_zarr_product_doc(product_name: str = BASE_ZARR_PRODUCT) -> dict[str, Any]:
    return {
        "name": product_name,
        "description": "Changtan EFDC hourly water-quality Base Zarr indexed by Open Data Cube",
        "metadata_type": "eo3",
        "metadata": {"product": {"name": product_name}},
        "measurements": [
            {"name": name, **definition}
            for name, definition in BASE_ZARR_MEASUREMENTS.items()
        ],
    }


def semantic_dataset_doc(
    zarr_path: str | Path,
    product_name: str = SEMANTIC_PRODUCT,
) -> dict[str, Any]:
    path = Path(zarr_path)
    ds = open_zarr_like(path)
    semantic_type = str(ds.attrs.get("semantic_type", path.stem))
    time_start = _time_text(ds, 0)
    time_end = _time_text(ds, -1)
    min_x, min_y, max_x, max_y = _bbox_from_zarr(ds)
    source_product = ds.attrs.get("source_product", BASE_ZARR_PRODUCT)
    if source_product == BASE_HOURTIF_PRODUCT:
        source_product = BASE_ZARR_PRODUCT
    properties = {
        "datetime": time_start,
        "dtr:start_datetime": time_start,
        "dtr:end_datetime": time_end,
        "semantic:type": semantic_type,
        "semantic:rule_id": ds.attrs.get("rule_id", semantic_type),
        "semantic:rule_version": ds.attrs.get("rule_version", "unknown"),
        "semantic:source_product": source_product,
        "semantic:operator": ds.attrs.get("operator"),
        "semantic:threshold": ds.attrs.get("threshold"),
        "semantic:upper_label": ds.attrs.get("upper_label"),
        "semantic:lower_label": ds.attrs.get("lower_label"),
        "semantic:primary_segment_policy": ds.attrs.get("primary_segment_policy"),
        "odc:file_format": "Zarr",
    }
    return {
        "$schema": "https://schemas.opendatacube.org/dataset",
        "id": deterministic_dataset_uuid(product_name, path.resolve(), time_start, time_end, semantic_type, properties["semantic:rule_version"]),
        "label": f"{product_name}_{semantic_type}",
        "product": {"name": product_name},
        "crs": "epsg:4326",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[min_x, min_y], [min_x, max_y], [max_x, max_y], [max_x, min_y], [min_x, min_y]]
            ],
        },
        "grids": {"default": _grid_from_zarr(ds)},
        "properties": {key: _jsonable(value) for key, value in properties.items() if value is not None},
        "location": file_uri(path),
        "measurements": {
            name: {"grid": "default"}
            for name in SEMANTIC_MEASUREMENTS
            if name in ds.data_vars
        },
    }


def base_hourtif_dataset_doc(
    workspace: str | Path,
    product_name: str = BASE_HOURTIF_PRODUCT,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    tif_dir = default_efdc_root(root) / "hourtif"
    sample = next(tif_dir.glob("*.tif"), None)
    if sample is None:
        raise FileNotFoundError(f"No EFDC TIF found in {tif_dir}")
    from lake_semantic_cube.io.efdc_tif import raster_grid

    grid = raster_grid(sample)
    time_start = "2025-10-01T01:00:00Z"
    time_end = "2025-10-08T01:00:00Z"
    variables = sorted({str(item["variable"]) for item in SEMANTIC_DEFINITIONS.values() if item.get("idx") is not None})
    return {
        "$schema": "https://schemas.opendatacube.org/dataset",
        "id": deterministic_dataset_uuid(product_name, tif_dir.resolve(), time_start, time_end),
        "label": f"{product_name}_169h",
        "product": {"name": product_name},
        "crs": "epsg:4326",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [grid.min_x, grid.min_y],
                    [grid.min_x, grid.max_y],
                    [grid.max_x, grid.max_y],
                    [grid.max_x, grid.min_y],
                    [grid.min_x, grid.min_y],
                ]
            ],
        },
        "grids": {
            "default": {
                "shape": [grid.height, grid.width],
                "transform": [
                    (grid.max_x - grid.min_x) / grid.width,
                    0.0,
                    grid.min_x,
                    0.0,
                    -(grid.max_y - grid.min_y) / grid.height,
                    grid.max_y,
                ],
            }
        },
        "properties": {
            "datetime": time_start,
            "dtr:start_datetime": time_start,
            "dtr:end_datetime": time_end,
            "odc:file_format": "GeoTIFF collection",
            "model:variables": json.dumps(variables),
        },
        "location": file_uri(tif_dir),
        "measurements": {"value": {"grid": "default"}},
    }


def base_zarr_dataset_doc(
    zarr_path: str | Path,
    product_name: str = BASE_ZARR_PRODUCT,
) -> dict[str, Any]:
    path = Path(zarr_path)
    ds = open_zarr_like(path)
    time_start = _time_text(ds, 0)
    time_end = _time_text(ds, -1)
    min_x, min_y, max_x, max_y = _bbox_from_zarr(ds)
    measurements = {name: {"grid": "default"} for name in ds.data_vars if name in BASE_ZARR_MEASUREMENTS}
    return {
        "$schema": "https://schemas.opendatacube.org/dataset",
        "id": deterministic_dataset_uuid(product_name, path.resolve(), time_start, time_end),
        "label": f"{product_name}_169h",
        "product": {"name": product_name},
        "crs": "epsg:4326",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[min_x, min_y], [min_x, max_y], [max_x, max_y], [max_x, min_y], [min_x, min_y]]
            ],
        },
        "grids": {"default": _grid_from_zarr(ds)},
        "properties": {
            "datetime": time_start,
            "dtr:start_datetime": time_start,
            "dtr:end_datetime": time_end,
            "odc:file_format": "Zarr",
            "model:variables": json.dumps(list(measurements)),
            "model:vertical_reference": ds.attrs.get("vertical_reference"),
            "model:source": ds.attrs.get("source"),
        },
        "location": file_uri(path),
        "measurements": measurements,
    }


def write_yaml(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")


def semantic_zarr_paths(root: Path) -> list[Path]:
    paths = []
    for definition in SEMANTIC_DEFINITIONS.values():
        zarr = definition.get("semantic_zarr")
        if zarr:
            path = root / str(zarr)
            if path.exists():
                paths.append(path)
    return paths


def build_odc_docs(root: str | Path, output_dir: str | Path) -> dict[str, list[Path]]:
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    product_dir = output_dir / "products"
    dataset_dir = output_dir / "datasets"
    semantic_product = product_dir / "changtan_vertical_semantic_real.product.yaml"
    base_product = product_dir / "changtan_efdc_hourtif_real.product.yaml"
    base_zarr_product = product_dir / "changtan_base_zarr_real.product.yaml"
    base_dataset = dataset_dir / "changtan_efdc_hourtif_real_169h.odc-metadata.yaml"
    base_zarr_dataset = dataset_dir / "changtan_base_zarr_real_169h.odc-metadata.yaml"

    write_yaml(semantic_product, semantic_product_doc())
    write_yaml(base_product, base_hourtif_product_doc())
    write_yaml(base_zarr_product, base_zarr_product_doc())
    write_yaml(base_dataset, base_hourtif_dataset_doc(root))

    products = [base_product, base_zarr_product, semantic_product]
    datasets = [base_dataset]
    base_zarr_path = root / "real_output" / "base_changtan_efdc_169h.zarr"
    if base_zarr_path.exists():
        write_yaml(base_zarr_dataset, base_zarr_dataset_doc(base_zarr_path))
        datasets.append(base_zarr_dataset)

    semantic_datasets = []
    for zarr_path in semantic_zarr_paths(root):
        doc = semantic_dataset_doc(zarr_path)
        dataset_path = dataset_dir / f"{doc['label']}.odc-metadata.yaml"
        write_yaml(dataset_path, doc)
        semantic_datasets.append(dataset_path)
    return {
        "products": products,
        "datasets": [*datasets, *semantic_datasets],
    }


def register_odc_docs(paths: dict[str, list[Path]], datacube_exe: str | Path | None, root: str | Path) -> list[dict[str, Any]]:
    indexer = OpenDataCubeIndexer(datacube_exe=datacube_exe, cwd=root)
    results = []
    for product in paths["products"]:
        result = indexer.product_add(product)
        results.append(
            {
                "kind": "product",
                "path": str(product),
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
    for dataset in paths["datasets"]:
        result = indexer.dataset_add(dataset)
        results.append(
            {
                "kind": "dataset",
                "path": str(dataset),
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
    return results
