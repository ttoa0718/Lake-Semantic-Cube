# Troubleshooting

## ODC Database Connection

If `datacube product list` fails, verify the external ODC configuration and PostgreSQL service. This repository does not include database credentials.

## Product Not Registered

Run `datacube product list` and add the product YAML from `odc_output/products/` before adding datasets.

## Dataset Not Discovered

Run `datacube dataset search product=<product_name>` and check that dataset `location` fields point to readable Zarr or GeoTIFF paths on the current machine.

## Zarr Path Problems

Generated dataset YAML may contain machine-specific locations. Regenerate metadata with `python -m lake_semantic_cube index-odc --output-dir odc_output` after moving data.

## CRS or Coordinate Mismatch

The current ODC examples use `epsg:4326`. Real source data must have coordinates consistent with the query points or bounding boxes passed to `QueryRequest`.

## Missing Dependencies

Install `requirements.txt` or create `environment.yml`. Real Zarr output requires `zarr`; tests can exercise some paths with the package fallback, but production use should install Zarr.

## Dask/Zarr Compatibility

The current code uses xarray/Zarr directly and does not require Dask-specific APIs. If Zarr writing fails, check the installed xarray and zarr versions in the active environment.
