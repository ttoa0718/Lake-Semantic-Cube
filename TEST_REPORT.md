# Test Report

- Date: 2026-09-16
- Working directory: `softwarex/`
- Python version: Python 3.12.4
- Command: `python -m pytest`
- Total tests: 10
- Passed: 10
- Failed: 0
- Skipped: 0

## CLI Smoke Checks

- `python -m lake_semantic_cube --help`: passed.
- `python -m lake_semantic_cube demo --output ..\demo_output_release_check`: passed; produced `point_rows = 4` and `region_rows = 1`.

## Notes

Pytest emitted 2 cache warnings because it could not create `.pytest_cache` in the local working directory. A direct demo run writing a new folder inside `softwarex/` also hit local Windows write permission denial in this workspace. Running the same demo to the writable parent workspace succeeded. This appears to be a local filesystem permission issue, not a software test failure.
