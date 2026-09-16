# Data Preparation

## Supported Current Paths

- EFDC hourly GeoTIFF files are parsed by `src/lake_semantic_cube/io/efdc_tif.py`.
- Base Zarr can be created from in-memory arrays with `build_base_zarr_from_arrays`.
- Real Changtan EFDC hourly GeoTIFF to Base Zarr is implemented by `scripts/build_real_base_zarr.py` and `python -m lake_semantic_cube build-real-base`.
- Profile CSV/XLS/XLSX reading is implemented by `ProfileAdapter`.
- Surface Zarr writing is implemented by `build_surface_zarr_from_arrays`.

## Workflow

```text
GeoTIFF or array data -> Base Zarr -> ODC metadata -> semantic rule evaluation -> Semantic Zarr
```

Example real-data command:

```bash
python scripts/build_real_base_zarr.py --tif-dir efdc_hour/hourtif --output-zarr real_output/base_changtan_efdc_169h.zarr --start-hour 1 --end-hour 169
```

Large EFDC and remote-sensing datasets are not suitable for direct GitHub upload. Publish a minimal licensed subset separately if real-data reproduction is required.

## Minimal Changtan Sample

`examples/sample_data/` now contains a small real Changtan subset for repository review and ODC setup practice:

- `S2_MSI_20251103024511_S02093_r0010_fai.tif`
- `changtan_profile_buoy_point.xlsx`
- `changtan_reservoir_polygon.shp/.shx/.dbf/.prj`

This sample is useful for verifying file layout, raster readability, boundary metadata, and ODC registration of a small public dataset. It does not contain hourly multi-layer EFDC water-quality data, so it cannot reproduce the full vertical semantic workflow by itself.
