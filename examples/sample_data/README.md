# Changtan Minimal Sample Data

This directory contains a small real Changtan sample-data subset for repository review and ODC setup practice. It is intentionally tiny and is not sufficient to reproduce the full scientific Changtan EFDC experiments.

## Included Files

| File | Size | Purpose |
|---|---:|---|
| `S2_MSI_20251103024511_S02093_r0010_fai.tif` | 204,938 bytes | One Sentinel-2-derived FAI GeoTIFF over Changtan Reservoir. |
| `00ok-msi-RGB.pkl` | 113 bytes | Companion marker file from the same Sentinel-2 scene directory. |
| `changtan_profile_buoy_point.xlsx` | 2,620 bytes | Small profile-buoy station coordinate table. |
| `changtan_reservoir_polygon.shp/.shx/.dbf/.prj` | 69,733 bytes total | Changtan Reservoir boundary shapefile core files. The original `.xml` metadata is intentionally not included because it contains local GIS lineage paths. |

## Spatial Extent

The sample FAI GeoTIFF has 954 x 1644 pixels, `float32` values, and a nodata/fill value of approximately `9.969209968386869e+36`. It covers approximately:

- longitude: 120.988748 to 121.074447
- latitude: 28.515071 to 28.662754

## Checksums

```text
1AE5B13414FC831B4F66B87837F6100474128840010E7F4C3ABBC5CD8B18467A  00ok-msi-RGB.pkl
E2EF758FBC704D754D5160FB1FB3ED3D94C850486AA7F2106FA99F1D8DBDE2EF  changtan_profile_buoy_point.xlsx
860262DC0E425A27DDFEBB9EC3ABC35A264E59A247A372590F2772A31C59131F  changtan_reservoir_polygon.dbf
01FBF2C44B71EA8A0A0A4253817BC070539D7B073DA64FDBD4729C43B4C77415  changtan_reservoir_polygon.prj
41E5B7C2B938A3D4C507FF900CCF3A009D6E0184C9F150EBA145F1D589E55DF9  changtan_reservoir_polygon.shp
D0502969EC62BAA6EF0E37C53EAF547C52435BFBC73E861DD7390C64307B5CE8  changtan_reservoir_polygon.shx
3F13610F89940E35CB645C9A95DE3A9DDD17E52F3D05A9BABEE21B3F370B4DF2  S2_MSI_20251103024511_S02093_r0010_fai.tif
```

## What This Sample Can And Cannot Do

It can be used to verify repository data layout, raster readability, shapefile presence, station metadata, and ODC product/dataset registration with a small public file.

It cannot reproduce the full vertical semantic EFDC workflow because that requires hourly multi-layer EFDC water-quality GeoTIFF files or derived Base/Semantic Zarr products. For the software chain itself, run the packaged synthetic demo:

```bash
python -m lake_semantic_cube demo --output demo_output
```
