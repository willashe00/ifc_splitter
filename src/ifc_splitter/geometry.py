"""
Geometry helpers for resolving IFC local placements to global coordinates.
"""

from __future__ import annotations

import numpy as np
import ifcopenshell


def _axis2placement3d_to_matrix(placement) -> np.ndarray:
    """Convert an IfcAxis2Placement3D to a 4x4 homogeneous transform."""
    origin = np.array(placement.Location.Coordinates, dtype=float)
    z = np.array(placement.Axis.DirectionRatios, dtype=float) if placement.Axis else np.array([0, 0, 1.0])
    x = np.array(placement.RefDirection.DirectionRatios, dtype=float) if placement.RefDirection else np.array([1, 0, 0.0])

    # Orthonormalise
    z = z / np.linalg.norm(z)
    x = x - np.dot(x, z) * z
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)

    T = np.eye(4)
    T[:3, 0] = x
    T[:3, 1] = y
    T[:3, 2] = z
    T[:3, 3] = origin
    return T


def resolve_global_placement(element) -> np.ndarray:
    """
    Walk the IfcLocalPlacement chain and return the 4x4 global transform for
    an IFC product element.
    """
    matrices: list[np.ndarray] = []
    placement = element.ObjectPlacement
    while placement is not None and placement.is_a("IfcLocalPlacement"):
        rel = placement.RelativePlacement
        if rel.is_a("IfcAxis2Placement3D"):
            matrices.append(_axis2placement3d_to_matrix(rel))
        placement = placement.PlacementRelTo
    # Compose from root to leaf
    T = np.eye(4)
    for M in reversed(matrices):
        T = T @ M
    return T


def get_global_origin(element) -> np.ndarray:
    """Return the global XYZ origin of an element as a (3,) array."""
    T = resolve_global_placement(element)
    return T[:3, 3]