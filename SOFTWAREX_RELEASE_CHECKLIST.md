# SoftwareX Release Checklist

## A. Mandatory Before Submission

- Public GitHub repository: TODO - author confirmation required.
- Source code available: prepared under `softwarex/src/lake_semantic_cube/`.
- README.md: prepared.
- LICENSE.txt: prepared, copyright holder pending.
- Fixed version/release: `v0.1.0` proposed.
- Metadata C1-C8: prepared in `SOFTWAREX_METADATA.md`, with TODOs for repository/manual/email.
- Installation instructions: prepared.
- Runnable software: synthetic demo and tests run locally.
- Tests: `python -m pytest` passes 10 tests.
- Examples: prepared under `examples/`.

## B. Strongly Recommended

- CITATION.cff: prepared.
- Zenodo release / DOI: TODO after public release.
- CHANGELOG: prepared.
- Reproducibility guide: prepared.
- Minimal example data: synthetic demo plus a small real Changtan Sentinel-2/boundary/station subset are available; real EFDC vertical subset still requires author decision.
- Automated test instructions: prepared.
- Screenshots: TODO if required for submission package.

## C. Author Confirmation Required

- Public GitHub repository URL.
- Final release version.
- Copyright holder.
- Support email.
- Zenodo DOI.
- Whether to publish a minimal Changtan EFDC vertical data subset separately.
- Whether to exclude or sanitize `real_output/`, `odc_output/`, `odc_output_cli/`, historical reports, and shapefile XML metadata before public release.
