"""
IFC Semantic Splitter — orchestration module.

Reads a comprehensive IFC model, classifies elements into semantic
categories, groups them by connectivity (piping) or spatial containment /
proximity (buildings), and writes each group as an isolated IFC file.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import ifcopenshell

from ..config import EQUIPMENT_TYPES
from ..grouping import group_piping_systems, group_building_systems
from .naming import name_piping_group, name_building_group, deduplicate_names
from .writer import write_ifc_subset


def split_ifc(
    input_path: str | Path,
    output_dir: str | Path,
    building_proximity: float | None = None,
) -> List[Tuple[str, Path]]:
    """
    Split a comprehensive IFC file into isolated semantic system models.

    Parameters
    ----------
    input_path : path to the source IFC file.
    output_dir : directory for the generated IFC subset files.
    building_proximity : override for the building clustering threshold
                         (metres).  ``None`` uses the default from config.

    Returns
    -------
    list of (model_name, output_path) tuples for every written file.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ifc_file = ifcopenshell.open(str(input_path))
    results: List[Tuple[str, Path]] = []

    # ------------------------------------------------------------------ #
    # 1. Piping systems — connectivity-based grouping
    # ------------------------------------------------------------------ #
    piping_groups = sorted(group_piping_systems(ifc_file), key=lambda g: min(g))
    piping_names = [
        name_piping_group(ifc_file, g, i)
        for i, g in enumerate(piping_groups, start=1)
    ]
    piping_names = deduplicate_names(piping_names)

    for name, group in zip(piping_names, piping_groups):
        out = output_dir / f"{name}.ifc"
        write_ifc_subset(ifc_file, group, out, model_name=name)
        results.append((name, out))
        print(f"  [piping]   {name:45s}  {len(group):3d} elements -> {out.name}")

    # ------------------------------------------------------------------ #
    # 2. Building systems — containment + proximity grouping
    # ------------------------------------------------------------------ #
    kwargs = {}
    if building_proximity is not None:
        kwargs["threshold"] = building_proximity

    building_groups = sorted(group_building_systems(ifc_file, **kwargs), key=lambda g: min(g))
    building_names = [
        name_building_group(ifc_file, g, i)
        for i, g in enumerate(building_groups, start=1)
    ]
    building_names = deduplicate_names(building_names)

    for name, group in zip(building_names, building_groups):
        out = output_dir / f"{name}.ifc"
        write_ifc_subset(ifc_file, group, out, model_name=name)
        results.append((name, out))
        print(f"  [building] {name:45s}  {len(group):3d} elements -> {out.name}")

    # ------------------------------------------------------------------ #
    # 3. Summary of discarded equipment
    # ------------------------------------------------------------------ #
    discarded = []
    for eq_type in EQUIPMENT_TYPES:
        for elem in ifc_file.by_type(eq_type):
            discarded.append(f"{elem.is_a()} #{elem.id()} ({elem.Name})")
    if discarded:
        print(f"\n  Discarded {len(discarded)} equipment entities:")
        for d in discarded:
            print(f"    - {d}")

    return results