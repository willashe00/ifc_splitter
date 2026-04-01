"""
Grouping algorithms for semantic system isolation.

Piping groups:  Connected-component analysis on the port-connectivity graph,
                restricted to IfcPipeSegment / IfcPipeFitting entities.

Building groups: Spatial proximity clustering on resolved global centroids
                 of IfcWall / IfcSlab / IfcBuildingElementProxy entities.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

import numpy as np
import ifcopenshell

from .config import (
    PIPING_TYPES,
    BUILDING_TYPES,
    EQUIPMENT_TYPES,
    BUILDING_PROXIMITY_THRESHOLD,
)
from .geometry import get_global_origin


# ======================================================================= #
# Union-Find for connected components
# ======================================================================= #
class _UnionFind:
    def __init__(self):
        self._parent: Dict[int, int] = {}
        self._rank: Dict[int, int] = {}

    def find(self, x: int) -> int:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def components(self, ids: set[int]) -> Dict[int, Set[int]]:
        groups: Dict[int, Set[int]] = defaultdict(set)
        for i in ids:
            groups[self.find(i)].add(i)
        return dict(groups)


# ======================================================================= #
# Piping grouping — port connectivity
# ======================================================================= #
def _get_port_parent_map(ifc_file: ifcopenshell.file) -> Dict[int, int]:
    """Map port step-id → parent element step-id via IfcRelNests."""
    port_to_parent = {}
    for rel in ifc_file.by_type("IfcRelNests"):
        parent = rel.RelatingObject
        for child in rel.RelatedObjects:
            if child.is_a("IfcDistributionPort"):
                port_to_parent[child.id()] = parent.id()
    return port_to_parent


def group_piping_systems(ifc_file: ifcopenshell.file) -> List[Set[int]]:
    """
    Return a list of sets, each containing step-ids of piping elements
    (IfcPipeSegment + IfcPipeFitting) that form a continuously connected
    pipe run.  Equipment-type neighbours are excluded (edges to equipment
    are severed so pipe runs terminate at equipment boundaries).
    """
    port_to_parent = _get_port_parent_map(ifc_file)

    # Collect the step-ids of all piping elements
    piping_ids: Set[int] = set()
    for ifc_type in PIPING_TYPES:
        for elem in ifc_file.by_type(ifc_type):
            piping_ids.add(elem.id())

    uf = _UnionFind()
    for elem_id in piping_ids:
        uf.find(elem_id)  # ensure registration

    # Walk port connections; only union piping ↔ piping edges
    for rel in ifc_file.by_type("IfcRelConnectsPorts"):
        parent_a = port_to_parent.get(rel.RelatingPort.id())
        parent_b = port_to_parent.get(rel.RelatedPort.id())
        if parent_a is None or parent_b is None:
            continue
        if parent_a in piping_ids and parent_b in piping_ids:
            uf.union(parent_a, parent_b)

    components = uf.components(piping_ids)
    return list(components.values())


# ======================================================================= #
# Building grouping — spatial containment + proximity fallback
# ======================================================================= #
def _get_building_containment_map(
    ifc_file: ifcopenshell.file,
) -> Dict[int, int]:
    """
    Map building-element step-id → IfcBuilding step-id using the
    IfcRelContainedInSpatialStructure hierarchy.  Elements not directly
    contained in an IfcBuilding are omitted.
    """
    elem_to_building: Dict[int, int] = {}
    for rel in ifc_file.by_type("IfcRelContainedInSpatialStructure"):
        container = rel.RelatingStructure
        if not container.is_a("IfcBuilding"):
            continue
        for elem in rel.RelatedElements:
            if elem.is_a() in BUILDING_TYPES:
                elem_to_building[elem.id()] = container.id()
    return elem_to_building


def group_building_systems(
    ifc_file: ifcopenshell.file,
    threshold: float = BUILDING_PROXIMITY_THRESHOLD,
) -> List[Set[int]]:
    """
    Return groups of building-element step-ids.

    Strategy (two-tier):
      1. Elements that share an IfcBuilding spatial container are
         unconditionally grouped together (this respects the semantic
         hierarchy authored in the BIM model and avoids splitting tall
         structures like a containment wall + dome).
      2. Any building-type elements NOT assigned to an IfcBuilding
         (e.g. sitting directly on the IfcSite) are clustered by
         single-linkage spatial proximity as a fallback.
    """
    containment = _get_building_containment_map(ifc_file)

    # --- Tier 1: IfcBuilding-based groups ----------------------------- #
    bldg_groups: Dict[int, Set[int]] = defaultdict(set)
    orphans: List[tuple] = []  # (step_id, origin)

    for ifc_type in BUILDING_TYPES:
        for elem in ifc_file.by_type(ifc_type):
            eid = elem.id()
            if eid in containment:
                bldg_groups[containment[eid]].add(eid)
            else:
                origin = get_global_origin(elem)
                orphans.append((eid, origin))

    groups: List[Set[int]] = list(bldg_groups.values())

    # --- Tier 2: proximity clustering for orphans --------------------- #
    if orphans:
        n = len(orphans)
        uf = _UnionFind()
        for eid, _ in orphans:
            uf.find(eid)
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(orphans[i][1] - orphans[j][1])
                if dist <= threshold:
                    uf.union(orphans[i][0], orphans[j][0])
        orphan_ids = {o[0] for o in orphans}
        groups.extend(uf.components(orphan_ids).values())

    return groups