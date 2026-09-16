# Implementation Status

This document records the current implementation status against the manuscript method body. Legacy benchmark code and M1-M4 outputs were preserved and not recalculated.

## Implemented

| Method component | Status | Main files |
|---|---|---|
| Model Base Zarr | Implemented | `src/lake_semantic_cube/io/model_zarr.py` |
| Surface Zarr | Implemented | `src/lake_semantic_cube/io/surface.py`, `src/lake_semantic_cube/io/surface_zarr.py` |
| Profile CSV/XLS/XLSX adapter | Implemented | `src/lake_semantic_cube/io/profile.py` |
| VerticalReference | Implemented | `src/lake_semantic_cube/vertical/reference.py` |
| SemanticRule JSON | Implemented | `src/lake_semantic_cube/semantics/parser.py`, `rules/*.json` |
| SemanticEvaluator | Implemented | `src/lake_semantic_cube/semantics/evaluator.py` |
| Continuous semantic segment detection | Implemented | `src/lake_semantic_cube/semantics/segment.py` |
| Semantic Zarr writer | Implemented | `src/lake_semantic_cube/semantic_product/writer.py` |
| Base and semantic EO3-like metadata | Implemented | `src/lake_semantic_cube/catalog/base_product.py`, `src/lake_semantic_cube/catalog/semantic_product.py` |
| Deterministic UUID | Implemented | `src/lake_semantic_cube/catalog/eo3.py` |
| ODC-style catalog adapter | Implemented | `src/lake_semantic_cube/catalog/odc.py` |
| QueryRequest Q={T,P,S,V,D} | Implemented | `src/lake_semantic_cube/query/request.py` |
| QueryPlanner | Implemented | `src/lake_semantic_cube/query/planner.py` |
| Semantic point query | Implemented | `src/lake_semantic_cube/query/point.py` |
| Actual-depth point query | Implemented | `src/lake_semantic_cube/query/actual_depth.py` |
| Region semantic query | Implemented | `src/lake_semantic_cube/query/region.py` |
| Streamlit GUI | Implemented | `gui/app.py` |
| Local map UI with Changtan shp hit-testing | Implemented | `src/lake_semantic_cube/ui/app.py` |
| Real EFDC TIF point profile reader | Implemented | `src/lake_semantic_cube/io/efdc_tif.py` |
| Real DOX hypoxia Semantic Zarr | Implemented | `real_output/semantic_hypoxia_dox_169h.zarr` |
| Real-data map point query | Implemented | `src/lake_semantic_cube/ui/app.py` |
| Real-data map region query | Implemented | `src/lake_semantic_cube/ui/app.py` |

## Real Data Sources

| Data source | Current use |
|---|---|
| `efdc_hour/hourtif` | Real EFDC TIF point profiles and regional semantic thickness maps |
| `efdc_hour/Changtan_wq_expend.zarr` | Existing real COD/NHX Base Zarr reference |
| `real_output/semantic_hypoxia_dox_169h.zarr` | Real DOX hypoxia vertical semantic index for 169 model hours |
| `tif/S02093_Changtan` | Real Sentinel-2 RGB/Chla/SDD/Bloom map preview and point sampling |
| `剖面浮标.csv` | Real buoy observation table |
| `changtan_profile_buoy_point.xlsx` | Real buoy station coordinates |

## Streamlit GUI Pages

The manuscript-facing GUI is available with:

```powershell
streamlit run gui/app.py
```

or:

```powershell
lake-semantic gui --port 8501
```

The GUI contains these pages:

- Project & Data
- Semantic Rules
- Semantic Zarr
- ODC Catalog
- Point Query
- Region Query
- Runtime Log

The GUI calls package APIs directly and keeps semantic parsing, evaluation, planning, and querying in the core modules.

## Preserved but Not Mutated

- Existing PostgreSQL/ODC datasets.
- Existing TIF/Zarr products in the legacy experiment folders.
- Existing M1-M4 benchmark scripts and results.

## Current Real-Data Query Behavior

The local map UI at `http://127.0.0.1:5050` now uses real data by default:

- Hypoxia point query reads semantic boundaries from `real_output/semantic_hypoxia_dox_169h.zarr`.
- The environmental time-depth image reads values from real EFDC TIF files in `efdc_hour/hourtif`.
- Region query reads real EFDC TIF files and computes semantic thickness maps for the selected area.
- Remote sensing values are sampled from the real Sentinel-2 Chla/SDD/Bloom TIF files.
- Buoy station positions are loaded from `changtan_profile_buoy_point.xlsx`; buoy observations are loaded from `剖面浮标.csv`.

## Still Requiring Scientific Confirmation

- Authoritative EFDC vertical-layer definition and layer order.
- Final bathymetry source for real Changtan depth mapping.
- Final percentile reference scope for semantic thresholds.
- Production policy for writing semantic products into PostgreSQL-backed ODC.
- Long-period Semantic Zarr generation for 2160-hour COD/NHX products if those are required for the final experiment.
