# Architecture

```text
Environmental Data
      |
      v
Base Product
      |
      v
Base Zarr
      |
      v
Vertical Reference
      |
      v
Semantic Rule
      |
      v
Semantic Evaluator
      |
      v
Semantic Object
      |
      v
Semantic Zarr
      |
      v
Vertical Semantic Index
      |
      v
ODC Catalog
      |
      v
QueryRequest Q={T,P,S,V,D}
      |
      v
QueryPlanner
      |
      v
Depth -> Layer -> Chunk
      |
      v
Base Zarr Access
      |
      v
Point / Actual-Depth / Region Query
```

## Main Modules

- `io/model_zarr.py`: builds Base Zarr products and time partitions.
- `io/model_tif.py`: parses EFDC GeoTIFF names and unifies model-hour conversion.
- `io/surface.py`: builds surface-only products with explicit surface vertical support.
- `io/profile.py`: loads profile CSV/XLS/XLSX observations while preserving actual measured depths.
- `vertical/reference.py`: maps model layers to actual depth and depth intervals back to candidate layers.
- `semantics/parser.py`: validates JSON semantic rules.
- `semantics/evaluator.py`: evaluates threshold, percentile, and gradient rules.
- `semantics/segment.py`: detects continuous vertical intervals and selects the thickest primary interval.
- `semantic_product/writer.py`: writes Semantic Zarr products.
- `catalog/base_product.py`: generates base-product EO3-like metadata.
- `catalog/semantic_product.py`: generates semantic ODC-style metadata.
- `query/planner.py`: resolves semantic requests to depth, layer, and chunk ranges.
- `query/point.py`, `query/actual_depth.py`, and `query/region.py`: execute semantic point, requested-depth point, and region queries.
- `gui/app.py`: provides the Streamlit GUI for the manuscript method chain.
