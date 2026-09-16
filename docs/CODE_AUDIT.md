# Code Audit

This audit separates active method software from legacy benchmark material. Legacy benchmark files were not rewritten or rerun.

| File or folder | Role | Input | Output | Continue use | New software | Legacy benchmark |
|---|---|---|---|---|---|---|
| `src/lake_semantic_cube/` | Formal method implementation | Config, arrays, rules, Base Zarr | Semantic Zarr, plans, query results | Yes | Yes | No |
| `lake_semantic_cube/` | Root shim for `python -m lake_semantic_cube` | Local source tree | CLI entry | Yes | Yes | No |
| `rules/*.json` | Default semantic rules | Rule parameters | Validated SemanticRule | Yes | Yes | No |
| `configs/*.yaml` | Demo and Changtan example configs | Paths, variables, vertical setup | Runtime configuration | Yes | Yes | No |
| `tests/` | Synthetic formal tests | Synthetic arrays | pytest results | Yes | Yes | No |
| `lake_semantic_experiment/` | Earlier semantic prototype | Model Zarr, TIF, buoy CSV | Prototype Semantic Zarr and local catalog | Reference | Partly superseded | No |
| `codex_test/` | Curated ODC/Zarr benchmark package | Existing benchmark CSV | Figures and performance summaries | Keep | No | Yes |
| `datacube-core/changtan/*.product.yaml` | Existing ODC products | Product definitions | ODC product registration | Keep | Adapter reference | Yes |
| `datacube-core/changtan/dataset*` | Existing ODC dataset metadata | YAML metadata | ODC dataset indexing | Keep | Adapter reference | Yes |
| `datacube-core/changtan/tif_dataset*` | Existing TIF dataset metadata | YAML metadata | ODC TIF indexing | Keep | Adapter reference | Yes |
| `history/legacy_pipeline_scripts/Atif2zarr.py` | Earlier TIF to Zarr code | GeoTIFFs | Zarr | Archive | Logic absorbed | No |
| `history/legacy_pipeline_scripts/B1make_odc_datasets_for_tif_hourly.py` | Earlier TIF metadata generator | TIF files | ODC YAML | Archive | Reference | Yes |
| `history/legacy_pipeline_scripts/B1generate_zarr_12parts_yaml.py` | Earlier partition metadata | Zarr parts | ODC YAML | Archive | Reference | Yes |
| `history/legacy_pipeline_scripts/Dcompare_polygon20260519.py` | Published region benchmark | Existing ODC/TIF/Zarr | Benchmark CSV | Keep archived | No | Yes |
| `history/legacy_pipeline_scripts/Dcompare_point20260520.py` | Published point benchmark variant | Existing ODC/TIF/Zarr | Benchmark CSV | Keep archived | No | Yes |
| `history/old_benchmark_outputs/` | Historical benchmark outputs | Earlier runs | CSV summaries | Keep archived | No | Yes |
| `history/diagnostics/` | One-off diagnostics | ODC/TIF outputs | Debug logs | Archive | No | No |
| `tif/` | Source remote sensing and TIF data | GeoTIFFs | Data input | Yes | Input adapter | No |
| `剖面浮标.csv` | Profile buoy source | CSV | Profile adapter input | Yes | Yes | No |
| `焦亚沁-基于垂向语义层索引的湖泊三维水环境数据组织与访问方法-0913.docx` | Manuscript | Word document | Manuscript | Yes | No | No |

## ODC Environment Check

The original development environment used a local ODC conda environment. For public release, configure ODC externally, place `datacube` on `PATH` or set `DATACUBE_EXE`, and set `PROJ_LIB`/`PROJ_DATA` only if required by the target geospatial stack.

Observed products include `changtan_wq_zarr_hourly_multi_expend` with 12 datasets and `changtan_wq_tif_hourly_indexed_expend_v2` with 43200 datasets.
