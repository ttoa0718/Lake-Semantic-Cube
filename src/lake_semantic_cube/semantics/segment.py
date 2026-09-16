from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Segment:
    layer_start: int
    layer_end: int
    layer_count: int
    z_top: float
    z_bottom: float
    thickness: float
    core_depth: float


def detect_segments(
    mask: np.ndarray,
    layer_tops: np.ndarray,
    layer_bottoms: np.ndarray,
    min_continuous_layers: int = 1,
    min_thickness: float = 0.0,
) -> list[Segment]:
    """Detect continuous True intervals in one vertical profile."""
    flags = np.asarray(mask, dtype=bool)
    tops = np.asarray(layer_tops, dtype="float64")
    bottoms = np.asarray(layer_bottoms, dtype="float64")
    if flags.ndim != 1:
        raise ValueError("mask must be one-dimensional")
    if not (len(flags) == len(tops) == len(bottoms)):
        raise ValueError("mask and layer bounds must have matching lengths")
    segments: list[Segment] = []
    start: int | None = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        if start is not None and ((not flag) or i == len(flags) - 1):
            end = i - 1 if not flag else i
            count = end - start + 1
            z_top = float(np.nanmin(tops[start : end + 1]))
            z_bottom = float(np.nanmax(bottoms[start : end + 1]))
            thickness = z_bottom - z_top
            if count >= min_continuous_layers and thickness >= min_thickness:
                segments.append(
                    Segment(
                        layer_start=start,
                        layer_end=end,
                        layer_count=count,
                        z_top=z_top,
                        z_bottom=z_bottom,
                        thickness=float(thickness),
                        core_depth=float((z_top + z_bottom) / 2.0),
                    )
                )
            start = None
    return segments


def primary_segment(segments: list[Segment]) -> Segment | None:
    """Return the thickest segment, preserving segment_count separately."""
    if not segments:
        return None
    return max(segments, key=lambda item: item.thickness)
