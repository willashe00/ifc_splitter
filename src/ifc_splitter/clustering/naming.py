"""
Naming utilities — generate human-readable model names from element sets,
with deduplication to prevent filename collisions.
"""

from __future__ import annotations

from collections import Counter
from typing import Set

import ifcopenshell


def name_piping_group(
    ifc_file: ifcopenshell.file,
    element_ids: Set[int],
    index: int,
) -> str:
    """
    Derive a descriptive name for a piping group.

    If the pipe segment names contain a recognisable run label
    (e.g. "HL-A to SG-PC-IN"), use it; otherwise fall back to a
    numbered label.
    """
    labels: set[str] = set()
    for eid in element_ids:
        elem = ifc_file.by_id(eid)
        name = elem.Name or ""
        if " from " in name:
            run_label = name.split(" from ", 1)[1]
            if run_label != "None to None":
                labels.add(run_label)

    if labels:
        return "piping_" + "__".join(sorted(labels)).replace(" ", "_")
    return f"piping_run_{index:02d}"


def name_building_group(
    ifc_file: ifcopenshell.file,
    element_ids: Set[int],
    index: int,
) -> str:
    """
    Derive a descriptive name for a building group.

    Checks if the elements include recognisable containment components
    (cylindrical wall, dome proxy, base-slab) or rectangular walls.
    """
    has_dome = False
    has_containment_wall = False
    wall_count = 0

    for eid in element_ids:
        elem = ifc_file.by_id(eid)
        if elem.is_a("IfcBuildingElementProxy"):
            if elem.Name and "Dome" in elem.Name:
                has_dome = True
        elif elem.is_a("IfcWall"):
            wall_count += 1
            if elem.Name and "Containment" in elem.Name:
                has_containment_wall = True

    if has_containment_wall or has_dome:
        return "nuclear_containment"
    if wall_count >= 2:
        return "turbine_building"
    return f"building_group_{index:02d}"


def deduplicate_names(names: list[str]) -> list[str]:
    """
    Append numeric suffixes to duplicate names.

    ['piping_run_01', 'piping_run_01', 'foo']
      -> ['piping_run_01_a', 'piping_run_01_b', 'foo']
    """
    counts = Counter(names)
    duplicates = {n for n, c in counts.items() if c > 1}

    suffix_tracker: dict[str, int] = {}
    result = []
    for name in names:
        if name in duplicates:
            idx = suffix_tracker.get(name, 0) + 1
            suffix_tracker[name] = idx
            result.append(f"{name}_{idx:02d}")
        else:
            result.append(name)
    return result