from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "lake_semantic_cube"
if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))

__version__ = "0.1.0"

from .query.request import BBox, Point, QueryRequest
from .vertical.reference import VerticalReference

__all__ = ["BBox", "Point", "QueryRequest", "VerticalReference"]
