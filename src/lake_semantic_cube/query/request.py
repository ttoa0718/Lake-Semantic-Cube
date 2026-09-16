from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class BBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class QueryRequest:
    """Formal Q={T,P,S,V,D} semantic query request."""

    time: tuple[str, str]
    space: Point | BBox
    semantic: str
    variables: tuple[str, ...]
    product_type: Literal["model", "surface", "profile"] = "model"
