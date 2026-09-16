# Public Release Checklist

## Cleaned Or Prepared

- README no longer documents local Windows data or conda paths.
- Public ODC examples are in `odc/` with placeholder/relative locations.
- `.env.example` uses environment variables and placeholders.
- `src/lake_semantic_cube/catalog/odc_core.py` now uses `DATACUBE_EXE` or `datacube` instead of a hard-coded local ODC path.
- GUI ODC defaults now use `DATACUBE_EXE`, `LAKE_SEMANTIC_PYTHON`, or the current Python interpreter.

## Still Requires Author Review Before Public GitHub Release

- Generated `odc_output/` and `odc_output_cli/` contain machine-specific dataset locations and should be regenerated, excluded, or sanitized before public release.
- `real_output/catalog.json` contains local dataset paths and should not be published as-is.
- Existing historical/report files may mention local paths; they should be excluded from the public release unless sanitized.
- Shapefile XML metadata under `ctshp/` contains historical local GIS lineage paths; remove XML metadata or sanitize before release if the shapefile is published.
- Large local EFDC, full remote-sensing scene collections, and generated outputs should not be committed to GitHub. The curated `examples/sample_data/` subset is intentionally small and excludes shapefile XML metadata with local GIS lineage.

## Sensitive Information Scan

The scan looked for drive paths, Windows user paths, password/secret/token/API-key terms, private IP ranges, and local database hints. No actual password was copied into this report. `localhost` appears only in example configuration with `password_env: LSC_PG_PASSWORD`.
