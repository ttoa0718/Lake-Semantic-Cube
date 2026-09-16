# Reproducibility

## Example 1: Base Zarr Construction

```bash
python examples/01_build_base_zarr.py
```

For real Changtan EFDC GeoTIFF files:

```bash
python scripts/build_real_base_zarr.py --tif-dir efdc_hour/hourtif --output-zarr real_output/base_changtan_efdc_169h.zarr --start-hour 1 --end-hour 169
```

## Example 2: Semantic Zarr Generation

```bash
python examples/02_build_semantic_zarr.py
```

For real EFDC hourly GeoTIFF-derived semantic products:

```bash
python scripts/build_real_hourtif_semantic.py --tif-dir efdc_hour/hourtif --output-zarr real_output/semantic_hypoxia_dox_169h.zarr --catalog real_output/catalog.json --semantic hypoxia_layer --start-hour 1 --end-hour 169
```

## Example 3: ODC Registration

```bash
python -m lake_semantic_cube index-odc --output-dir odc_output
datacube product add odc_output/products/changtan_vertical_semantic_real.product.yaml
datacube dataset add odc_output/datasets/changtan_vertical_semantic_real_hypoxia_layer.odc-metadata.yaml
```

## Example 4: Point-Based Semantic Query

```bash
python examples/example_query_point.py
```

## Example 5: Region-Scale Semantic Thickness Analysis

```bash
python examples/example_query_region.py
```

## Example 6: Automated Tests

```bash
python -m pytest
```

Current verified result: 10 passed, 0 failed, 0 skipped.

## Example 7: Performance Benchmark

No standalone performance benchmark script is part of the current SoftwareX release materials. Do not report benchmark numbers unless a separately verified benchmark workflow is added and run.
