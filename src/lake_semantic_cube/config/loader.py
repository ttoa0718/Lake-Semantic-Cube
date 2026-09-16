from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - yaml is optional at import time
    yaml = None


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON or YAML configuration file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(text)
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML configuration files")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a mapping: {p}")
    return data


def project_path(config: dict[str, Any], key: str, default: str) -> Path:
    """Resolve a path from config relative to project.root when present."""
    root = Path(config.get("project", {}).get("root", "."))
    value = config.get("paths", {}).get(key, default)
    path = Path(value)
    return path if path.is_absolute() else root / path
