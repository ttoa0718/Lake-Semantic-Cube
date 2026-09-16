# Open Data Cube Setup Tutorial

This tutorial explains how to configure Open Data Cube (ODC) for Lake Semantic Cube. ODC is used for product and dataset metadata cataloging and dataset discovery. Zarr/xarray or raster readers still perform the array data access.

## 1. What You Need

- Python environment with this package installed.
- Open Data Cube command-line tool: `datacube`.
- PostgreSQL server accessible from the machine running ODC.
- A local ODC configuration file with database credentials.

This repository does not store database host passwords, PostgreSQL passwords, tokens, or private server addresses.

## 2. Install The Python Package

From `softwarex/`:

```bash
conda env create -f environment.yml
conda activate lake-semantic-cube
python -m pip install -e .
```

If `datacube` is installed in another environment, either activate that environment before running ODC commands or set:

```bash
DATACUBE_EXE=/path/to/datacube
LAKE_SEMANTIC_PYTHON=/path/to/python
```

On Windows PowerShell:

```powershell
$env:DATACUBE_EXE="datacube"
$env:LAKE_SEMANTIC_PYTHON="python"
```

## 3. PostgreSQL And ODC Database

Create a PostgreSQL database and user using your institution's preferred security practice. A typical local-development outline is:

```bash
createdb datacube
createuser --interactive datacube
```

Then create the normal ODC configuration file for your platform. For example, in a user-level `datacube.conf`:

```ini
[datacube]
db_hostname: localhost
db_database: datacube
db_username: datacube
db_password: [SET LOCALLY, DO NOT COMMIT]
```

Initialize the index:

```bash
datacube system init
datacube product list
```

If `datacube product list` fails, solve the ODC/PostgreSQL connection first before registering Lake Semantic Cube products.

## 4. First Practice With The Minimal Changtan Sample

The repository includes a tiny real Changtan sample under `examples/sample_data/`:

- one Sentinel-2-derived FAI GeoTIFF;
- profile-buoy station coordinates;
- Changtan reservoir boundary shapefile core files.

Register the sample product and dataset:

```bash
datacube product add odc/products/changtan_s2_fai_sample.product.yaml
datacube dataset add odc/datasets/changtan_s2_fai_sample_20251103.odc-metadata.yaml
```

Verify discovery:

```bash
datacube product list
datacube dataset count changtan_s2_fai_sample
datacube dataset search product=changtan_s2_fai_sample
```

This step tests ODC itself using a small public file. It does not test the full vertical semantic EFDC workflow.

## 5. Generate Lake Semantic Cube ODC Metadata

For generated Base Zarr and Semantic Zarr outputs, create ODC YAML from the current project state:

```bash
python -m lake_semantic_cube index-odc --output-dir odc_output
```

This writes product YAML under `odc_output/products/` and dataset YAML under `odc_output/datasets/`. Dataset locations are machine-specific, so regenerate this directory after moving data or changing output paths.

## 6. Register Lake Semantic Cube Products

```bash
datacube product add odc_output/products/changtan_efdc_hourtif_real.product.yaml
datacube product add odc_output/products/changtan_base_zarr_real.product.yaml
datacube product add odc_output/products/changtan_vertical_semantic_real.product.yaml
```

The products represent:

- `changtan_efdc_hourtif_real`: EFDC hourly GeoTIFF collection metadata.
- `changtan_base_zarr_real`: Base Zarr product containing environmental variables such as `Chla`, `NHX`, `CODmn`, and `DOX`.
- `changtan_vertical_semantic_real`: Semantic Zarr product containing `occurrence`, `z_top`, `z_bottom`, `thickness`, `core_depth`, `segment_count`, `layer_start`, `layer_end`, and `semantic_mask`.

## 7. Register Datasets

Register only dataset YAML whose `location` points to data that exists on the current machine.

```bash
datacube dataset add odc_output/datasets/changtan_efdc_hourtif_real_169h.odc-metadata.yaml
datacube dataset add odc_output/datasets/changtan_base_zarr_real_169h.odc-metadata.yaml
datacube dataset add odc_output/datasets/changtan_vertical_semantic_real_hypoxia_layer.odc-metadata.yaml
```

The exact semantic dataset names depend on which Semantic Zarr products exist under `real_output/`.

## 8. Verify Product And Dataset Discovery

```bash
datacube product list
datacube dataset count changtan_efdc_hourtif_real
datacube dataset count changtan_base_zarr_real
datacube dataset count changtan_vertical_semantic_real
datacube dataset search product=changtan_vertical_semantic_real
```

For application-level ODC-backed query testing:

```bash
python scripts/query_real_odc.py --root . --mode point --semantic hypoxia_layer --x 121.034 --y 28.586
python scripts/query_real_odc.py --root . --mode region --semantic hypoxia_layer --min-x 121.02 --min-y 28.55 --max-x 121.05 --max-y 28.62
```

These commands require real Base/Semantic Zarr outputs and a working ODC index. They are not expected to run from only the minimal Sentinel-2 sample.

## 9. Recommended Workflow For Reviewers

1. Install the package.
2. Run `python -m lake_semantic_cube demo --output demo_output` to verify the software chain without ODC.
3. Configure PostgreSQL and initialize ODC.
4. Register `changtan_s2_fai_sample` to verify ODC setup with a tiny public file.
5. If real EFDC data are available, build Base/Semantic Zarr outputs, run `python -m lake_semantic_cube index-odc --output-dir odc_output`, and register the generated Lake Semantic Cube datasets.

## 10. Common ODC Errors

- Product already exists: ODC may report this when rerunning registration. Continue if the product definition is unchanged.
- Dataset location is unreadable: regenerate dataset YAML on the current machine or edit the location before indexing.
- `datacube product list` fails: check database credentials and PostgreSQL service.
- Dataset search returns no result: confirm that the dataset was added to the same ODC database and that product names match.
- CRS/coordinate mismatch: the sample FAI dataset uses `epsg:4326`; real EFDC/Zarr metadata should use coordinates matching the query inputs.
