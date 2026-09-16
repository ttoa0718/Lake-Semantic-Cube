# SoftwareX Release Audit

Audit scope: `softwarex/` release directory and adjacent current experiment package. Core scientific algorithms were not redesigned.

## Already Available

- Main source package: `src/lake_semantic_cube/`.
- Compatibility entry point: `lake_semantic_cube/__main__.py`.
- CLI: `src/lake_semantic_cube/cli.py` with `demo`, `build-real-base`, `index-odc`, `gui`, and `ui`.
- GUI/Web entries: `gui/app.py`, `src/lake_semantic_cube/ui/app.py`.
- Base Zarr construction: `src/lake_semantic_cube/io/model_zarr.py`, `scripts/build_real_base_zarr.py`.
- Semantic Zarr generation: `src/lake_semantic_cube/semantics/builder.py`, `semantic_product/writer.py`, `scripts/build_real_hourtif_semantic.py`.
- ODC product/dataset generation and optional registration: `src/lake_semantic_cube/catalog/odc_core.py`, `scripts/register_real_semantic_odc.py`.
- Point query: `src/lake_semantic_cube/query/point.py`, `scripts/query_semantic_zarr_point.py`.
- Region query: `src/lake_semantic_cube/query/region.py`.
- Semantic rules: `rules/*.json`.
- Automated tests: `tests/test_semantic_cube.py`.
- Packaging: `pyproject.toml`.

## Exists But Needed Improvement

- README existed but contained local paths and needed complete SoftwareX release structure.
- LICENSE existed as BSD-3-Clause but the requested release material now uses MIT with author-confirmation placeholder.
- CITATION existed but lacked repository/DOI TODOs and license alignment.
- ODC generated metadata existed under `odc_output/` and `odc_output_cli/` but contained local absolute paths.
- Docs existed but were partial and not organized around installation, ODC setup, usage, reproducibility, and troubleshooting.
- Examples existed as thin wrappers; public example names and README have been added.

## Missing Before This Pass

- `environment.yml`.
- `CHANGELOG.md`.
- `.env.example`.
- Public `odc/` directory with sanitized product/dataset examples.
- `TEST_REPORT.md`.
- `PUBLIC_RELEASE_CHECKLIST.md`.
- `RELEASE_NOTES_v0.1.0.md`.
- `SOFTWAREX_METADATA.md`.
- `SOFTWAREX_RELEASE_CHECKLIST.md`.

## Not Recommended For Submission-Preparation Scope

- Rewriting semantic rules or vertical-layer algorithms.
- Changing ODC/Zarr storage semantics.
- Adding unverified APIs, REST services, benchmarks, or new scientific products.
- Uploading full EFDC, remote-sensing, or generated Zarr datasets to GitHub.
- Converting historical scripts in `history/` or large `datacube-core/` material into the release package.
