from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lake_semantic_cube.catalog.odc_core import (
    build_odc_docs,
    register_odc_docs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and optionally register real Open Data Cube metadata.")
    parser.add_argument("--root", default=".", help="softwarex project root")
    parser.add_argument("--output-dir", default="odc_output", help="directory for generated ODC YAML")
    parser.add_argument("--datacube-exe", default=None, help="path to datacube.exe")
    parser.add_argument("--register", action="store_true", help="run datacube product add and dataset add")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paths = build_odc_docs(root, root / args.output_dir)
    payload: dict[str, Any] = {
        "products": [str(path) for path in paths["products"]],
        "datasets": [str(path) for path in paths["datasets"]],
    }
    if args.register:
        payload["registration"] = register_odc_docs(paths, args.datacube_exe, root)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
