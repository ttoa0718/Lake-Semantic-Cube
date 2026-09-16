# Usage

## Synthetic Demo

```bash
python -m lake_semantic_cube demo --output demo_output
```

## Point Query

```bash
python examples/example_query_point.py
```

The package API path is `QueryPlanner(...).plan(QueryRequest(..., space=Point(...)))` followed by `query_point(plan)`.

## Region Query

```bash
python examples/example_query_region.py
```

The package API path is `QueryPlanner(...).plan(QueryRequest(..., space=BBox(...)))` followed by `query_region(plan)`.

## Real Semantic Zarr Point Sampling

```bash
python scripts/query_semantic_zarr_point.py --zarr real_output/semantic_hypoxia_dox_169h.zarr --x 121.034 --y 28.586
```

## GUI/API

```bash
streamlit run gui/app.py
python -m lake_semantic_cube ui --port 5050
```

The Streamlit GUI exposes project, rule, Semantic Zarr, ODC, point query, and region query pages. The Flask UI provides a local map-oriented exploration interface.
