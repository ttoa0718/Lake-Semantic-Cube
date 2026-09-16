from __future__ import annotations


def chunk_range(start: int, stop_inclusive: int, chunk_size: int) -> list[int]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if stop_inclusive < start:
        return []
    return list(range(start // chunk_size, stop_inclusive // chunk_size + 1))


def get_chunk_indices(
    time_indices: tuple[int, int],
    layer_indices: tuple[int, int],
    y_indices: tuple[int, int],
    x_indices: tuple[int, int],
    chunk_shape: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int]]:
    """Return chunk coordinates intersecting time, layer, y, x index ranges."""
    ranges = [
        chunk_range(time_indices[0], time_indices[1], chunk_shape[0]),
        chunk_range(layer_indices[0], layer_indices[1], chunk_shape[1]),
        chunk_range(y_indices[0], y_indices[1], chunk_shape[2]),
        chunk_range(x_indices[0], x_indices[1], chunk_shape[3]),
    ]
    return [(t, z, y, x) for t in ranges[0] for z in ranges[1] for y in ranges[2] for x in ranges[3]]
