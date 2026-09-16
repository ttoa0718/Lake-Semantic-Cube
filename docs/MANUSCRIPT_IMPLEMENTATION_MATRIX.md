# Manuscript Implementation Matrix

| Manuscript method component | Software module | File position | Status | Test |
|---|---|---|---|---|
| Multi-source base products | Model, surface, profile adapters | `src/lake_semantic_cube/io/` | IMPLEMENTED | `tests/test_semantic_cube.py` |
| Base Zarr | Base Zarr writer and partitioner | `io/model_zarr.py` | IMPLEMENTED | `test_base_zarr_and_partition` |
| Unified time reference | Model hour conversion | `io/model_tif.py` | IMPLEMENTED | `test_filename_time_and_variable_config` |
| Unified variable metadata | Config schema | `config/schema.py`, `configs/*.yaml` | IMPLEMENTED | `test_filename_time_and_variable_config` |
| Unified vertical reference | VerticalReference | `vertical/reference.py` | IMPLEMENTED | `test_vertical_reference_and_dynamic_bathymetry` |
| Layer to actual depth | `layer_to_depth` | `vertical/reference.py` | IMPLEMENTED | `test_vertical_reference_and_dynamic_bathymetry` |
| Actual depth to layers | `depth_to_layers` | `vertical/reference.py` | IMPLEMENTED | `test_vertical_reference_and_dynamic_bathymetry` |
| Dynamic bathymetry | Grid layer bounds | `vertical/mapper.py` | IMPLEMENTED | `test_vertical_reference_and_dynamic_bathymetry` |
| Structured semantic rules | JSON parser | `semantics/parser.py`, `rules/` | IMPLEMENTED | `test_rule_parsing_invalid_absolute_percentile_gradient_and_logic` |
| Absolute threshold | Evaluator operators | `semantics/evaluator.py` | IMPLEMENTED | `test_semantic_evaluator_outputs_nan_and_primary_policy` |
| Percentile threshold | Global percentile | `semantics/evaluator.py` | IMPLEMENTED | `test_percentile_and_gradient_evaluation` |
| Gradient rule | Actual-depth gradient | `semantics/evaluator.py` | IMPLEMENTED | `test_percentile_and_gradient_evaluation` |
| Continuous segment detection | Segment detector | `semantics/segment.py` | IMPLEMENTED | `test_segments_multiple_primary_and_constraints` |
| Primary interval thickest | Primary selector | `semantics/segment.py` | IMPLEMENTED | `test_segments_multiple_primary_and_constraints` |
| Semantic object attributes | Evaluator output | `semantics/evaluator.py` | IMPLEMENTED | `test_semantic_evaluator_outputs_nan_and_primary_policy` |
| Semantic Zarr | Writer and builder | `semantic_product/writer.py`, `semantics/builder.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Vertical semantic index | `z_top`, `z_bottom`, `layer_start`, `layer_end` | Semantic Zarr variables | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| ODC semantic metadata | EO3-like docs | `catalog/semantic_product.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Deterministic UUID | UUID5 | `catalog/eo3.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| ODC catalog adapter | Metadata-only adapter | `catalog/odc.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| QueryRequest Q={T,P,S,V,D} | Query dataclass | `query/request.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| QueryPlanner | Semantic to chunk plan | `query/planner.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Semantic to actual depth | Semantic Zarr read | `query/planner.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Depth to layer | Semantic saved layers and VerticalReference support | `query/planner.py`, `vertical/reference.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Layer to chunk | Chunk index calculation | `query/chunks.py` | IMPLEMENTED | `test_chunk_indices_surface_profile_and_demo` |
| Point query | Semantic point access | `query/point.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| Region query | Dynamic semantic mask filtering | `query/region.py` | IMPLEMENTED | `test_semantic_zarr_metadata_uuid_and_query_chain` |
| PostgreSQL-backed ODC insertion | Real DB mutation | Existing Datacube CLI and future adapter | PARTIAL | ODC read-only check only |
| Real Changtan EFDC vertical definition | Scientific parameter | `docs/SCIENTIFIC_DECISIONS_REQUIRED.md` | PARTIAL | Not tested |
