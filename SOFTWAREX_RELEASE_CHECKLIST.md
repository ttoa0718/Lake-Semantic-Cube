# SoftwareX Release Checklist

## A. Mandatory Before Submission

- Public GitHub repository: https://github.com/ttoa0718/Lake-Semantic-Cube.
- Source code available: prepared under `softwarex/src/lake_semantic_cube/`.
- README.md: prepared.
- LICENSE.txt: prepared with Copyright (c) 2026 Yaqin Jiao.
- Fixed version/release: `v0.1.1`.
- Metadata C1-C8: prepared in `SOFTWAREX_METADATA.md`; Zenodo DOI is available.
- Installation instructions: prepared.
- Runnable software: synthetic demo and tests run locally.
- Tests: `python -m pytest` passes 10 tests.
- Examples: prepared under `examples/`.

## B. Strongly Recommended

- CITATION.cff: prepared.
- Zenodo release / DOI: https://doi.org/10.5281/zenodo.22795260.
- CHANGELOG: prepared.
- Reproducibility guide: prepared.
- Minimal example data: synthetic demo plus a small real Changtan Sentinel-2/boundary/station subset are available; real EFDC vertical subset still requires author decision.
- Automated test instructions: prepared.
- Screenshots: prepared under `docs/figures/`.

## C. Author Confirmation Required

- Final release version.
- Whether to publish a minimal Changtan EFDC vertical data subset separately.
- Whether to exclude or sanitize `real_output/`, `odc_output/`, `odc_output_cli/`, historical reports, and shapefile XML metadata before public release.
