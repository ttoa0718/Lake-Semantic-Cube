"""Input and base-product adapters."""

from .profile import ProfileAdapter, ProfileObservations, profile_depth_mask
from .surface import build_surface_zarr_from_arrays

__all__ = ["ProfileAdapter", "ProfileObservations", "build_surface_zarr_from_arrays", "profile_depth_mask"]
