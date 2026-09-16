# Release Notes: v0.1.0

## Software Purpose

Lake Semantic Cube organizes multidimensional lake water-environment data, generates dynamic vertical semantic products, and supports semantic point and regional queries.

## Main Features

- Base Zarr construction.
- Rule-based vertical semantic evaluation.
- Semantic Zarr generation.
- ODC-compatible metadata generation and optional registration.
- Minimal real Changtan sample data for ODC setup practice.
- Point semantic query and region-scale semantic thickness query.
- Streamlit GUI and Flask map UI.
- Automated tests and synthetic demo.

## Supported Workflows

- Synthetic end-to-end demo: `python -m lake_semantic_cube demo --output demo_output`.
- Real EFDC hourly GeoTIFF to Base Zarr.
- Real hourly GeoTIFF-derived semantic products.
- ODC product/dataset YAML generation.
- Point and regional semantic query examples.

## Known Limitations

- Full Changtan EFDC and remote-sensing collections are not bundled.
- ODC requires external PostgreSQL-backed setup.
- Real-data scripts assume the current EFDC GeoTIFF naming convention.
- No verified standalone benchmark is included in this release.

## Installation Documentation

See `README.md` and `docs/installation.md`.

## Example Workflows

See `examples/README.md` and `docs/reproducibility.md`.

## Test Status

Verified on Python 3.12.4 with `python -m pytest`: 10 passed, 0 failed, 0 skipped.
