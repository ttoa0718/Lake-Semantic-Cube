# Lake Semantic Cube

Lake Semantic Cube is a Python software framework for organizing multidimensional lake water-environment data, generating dynamic vertical semantic products, and supporting semantics-driven point and regional queries.

The current release is a research software prototype prepared for SoftwareX review. It implements Base Zarr construction, rule-based vertical semantic processing, Semantic Zarr generation, metadata cataloging through Open Data Cube-compatible YAML, point queries, region-scale semantic thickness queries, and two local user interfaces.

## Motivation

Fixed model layers do not directly express dynamic vertical environmental structures such as hypoxia layers, ammonium-enriched layers, cyanobacteria-enriched layers, or thermoclines. Lake Semantic Cube materializes these structures as semantic products so query workflows can ask for environmental objects instead of hard-coded layer numbers.

## Main Features

- Base Zarr construction from arrays and Changtan EFDC hourly GeoTIFF files.
- Rule-based vertical semantic processing from JSON rule files.
- Semantic Zarr generation with occurrence, boundary, thickness, core-depth, segment, and mask variables.
- ODC product and dataset YAML generation, plus optional registration through the `datacube` CLI.
- Point-based semantic query through `QueryPlanner` and `query_point`.
- Region-scale semantic thickness analysis through `QueryPlanner` and `query_region`.
- Streamlit GUI and Flask map UI.
- Automated pytest coverage for rule parsing, semantic evaluation, Zarr writing, query planning, point queries, region queries, profile/surface adapters, and the synthetic demo.

## Software Architecture

Raw EFDC, surface, or profile data -> Base products -> semantic processing -> Semantic Zarr -> ODC catalog or local JSON catalog -> `QueryPlanner` -> point/region query -> Web interface.

Open Data Cube performs metadata cataloging and dataset discovery. Zarr and xarray perform array storage and data access. Semantic Zarr stores derived vertical semantic information and does not replace the Base Zarr environmental variables.

## Repository Structure

```text
softwarex/
├── src/lake_semantic_cube/      # Main Python package
├── lake_semantic_cube/          # Compatibility package entry point
├── scripts/                     # Real-data build, registration, and query scripts
├── configs/                     # Example project configuration
├── rules/                       # JSON semantic rules
├── tests/                       # Automated tests
├── examples/                    # Minimal runnable examples
├── odc/                         # Public ODC product and dataset examples
├── docs/                        # Installation, ODC, usage, reproducibility notes
├── gui/                         # Streamlit GUI entry point
└── real_output/                 # Generated local outputs, not required for source release
```

## Installation

```bash
git clone [GITHUB URL TO BE ADDED]
cd Lake-Semantic-Cube/softwarex
conda env create -f environment.yml
conda activate lake-semantic-cube
python -m pip install -e .
```

For a pip-only development install:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Open Data Cube workflows require a working ODC installation and PostgreSQL-backed ODC database. Configure ODC outside this package, then ensure the `datacube` command is on `PATH`, or set:

```bash
DATACUBE_EXE=/path/to/datacube
```

If a separate Python interpreter is needed for ODC bridge commands, set:

```bash
LAKE_SEMANTIC_PYTHON=/path/to/python
```

## Open Data Cube Setup

Generate public-style ODC product and dataset YAML:

```bash
python -m lake_semantic_cube index-odc --output-dir odc_output
```

Register generated metadata in an initialized ODC database:

```bash
datacube product add odc_output/products/changtan_efdc_hourtif_real.product.yaml
datacube product add odc_output/products/changtan_base_zarr_real.product.yaml
datacube product add odc_output/products/changtan_vertical_semantic_real.product.yaml
datacube dataset add odc_output/datasets/changtan_efdc_hourtif_real_169h.odc-metadata.yaml
datacube product list
datacube dataset count changtan_vertical_semantic_real
datacube dataset search product=changtan_vertical_semantic_real
```

The sanitized examples in `odc/` include a minimal Sentinel-2 FAI sample product/dataset and placeholder semantic examples. Regenerate dataset YAML on the target machine before indexing full real-data products.

## Quick Start

Run the synthetic end-to-end demo, which does not require Changtan source data:

```bash
python -m lake_semantic_cube demo --output demo_output
```

The demo writes:

- `demo_output/base_model.zarr`
- `demo_output/semantic_hypoxia.zarr`
- `demo_output/catalog.json`
- `demo_output/point_query.csv`
- `demo_output/region_query.csv`

Run example wrappers:

```bash
python examples/01_build_base_zarr.py
python examples/02_build_semantic_zarr.py
python examples/example_query_point.py
python examples/example_query_region.py
```

## Semantic Rule Example

`rules/hypoxia.json` defines `hypoxia_layer` from `DOX < 2.0 mg/L` with at least two continuous layers and 1.0 m minimum thickness. Its output fields are `occurrence`, `z_top`, `z_bottom`, `thickness`, `core_depth`, `segment_count`, `layer_start`, and `layer_end`.

## Base Zarr and Semantic Zarr

Base Zarr stores environmental variables, typically with `time`, `layer`, `y`, and `x` dimensions. Semantic Zarr stores derived semantic-layer indices with `time`, `y`, `x`, and for `semantic_mask`, `layer`.

ODC catalogs dataset metadata and supports discovery by product, time, space, and semantic type. It does not accelerate Zarr array reads by itself; xarray/Zarr perform the actual array access.

## Point Query Example

```python
from lake_semantic_cube.cli import run_demo

summary = run_demo("demo_output")
print(summary["point_query_csv"])
```

The underlying package path is `QueryPlanner(...).plan(QueryRequest(..., space=Point(...)))` followed by `query_point(plan)`.

## Region Query Example

```python
from lake_semantic_cube.cli import run_demo

summary = run_demo("demo_output")
print(summary["region_query_csv"])
```

The underlying package path is `QueryPlanner(...).plan(QueryRequest(..., space=BBox(...)))` followed by `query_region(plan)`.

## Web Interface

Streamlit GUI:

```bash
streamlit run gui/app.py
```

or:

```bash
lake-semantic gui --port 8501
```

Local Flask map UI:

```bash
python -m lake_semantic_cube ui --port 5050
```

The Flask UI expects local Changtan data for full real-data operation and falls back only for selected visualization components.

## Tests

Tested on Python 3.12.4:

```bash
python -m pytest
```

Current result: 10 passed, 0 failed, 0 skipped, with 2 pytest cache warnings caused by local cache write permission.

## Example Data

The repository includes a minimal real Changtan sample under `examples/sample_data/`: one Sentinel-2-derived FAI GeoTIFF, profile-buoy station coordinates, and Changtan reservoir boundary shapefile core files. Large EFDC, remote-sensing scene collections, and generated Zarr products should not be uploaded to GitHub. Reviewers can run the synthetic demo without external data; scientifically meaningful vertical EFDC reproduction still requires an author-provided licensed EFDC subset or separately published data archive.

## Reproducibility

The main SoftwareX illustrative examples are documented in `docs/reproducibility.md`: Base Zarr construction, Semantic Zarr generation, ODC registration, point semantic query, region thickness analysis, and automated tests.

## Limitations

- Real Changtan EFDC and remote-sensing data are not bundled as a full public dataset.
- ODC registration requires an external PostgreSQL-backed ODC environment.
- Real-data scripts assume the EFDC hourly GeoTIFF naming convention parsed by `src/lake_semantic_cube/io/efdc_tif.py`.
- Incremental Semantic Zarr updates, rule migration tooling, automatic chunk optimization, REST deployment, and benchmark automation are future development items.

## Citation

See `CITATION.cff`.

## License

See `LICENSE.txt`. Copyright holder must be confirmed by the authors before release.

## Contact

[SUPPORT EMAIL TO BE CONFIRMED]
