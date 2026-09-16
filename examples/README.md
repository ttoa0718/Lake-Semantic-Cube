# Examples

These examples use the packaged synthetic demo so they can run without the full Changtan EFDC or remote-sensing datasets.

From the `softwarex/` directory:

```bash
python examples/01_build_base_zarr.py
python examples/02_build_semantic_zarr.py
python examples/example_query_point.py
python examples/example_query_region.py
```

All four commands call the same verified end-to-end demo in `lake_semantic_cube.cli.run_demo`. The demo creates `demo_output/base_model.zarr`, `demo_output/semantic_hypoxia.zarr`, a local `demo_output/catalog.json`, and CSV outputs for point and regional queries.

The full Changtan workflows require author-provided EFDC hourly GeoTIFF files following the naming convention parsed by `src/lake_semantic_cube/io/efdc_tif.py`. Do not treat the synthetic demo as a scientifically meaningful Changtan dataset.
