"""Vertical semantic indexing for lake water-environment data."""

__version__ = "0.1.1"

from .query.request import BBox, Point, QueryRequest
from .vertical.reference import VerticalReference

__all__ = ["BBox", "Point", "QueryRequest", "VerticalReference"]
