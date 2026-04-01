"""
IFC subset writer.

Given a source IFC file and a set of element step-ids, produce a new IFC
file that contains:
  - the standard project / site / building scaffold,
  - all selected product elements with their full geometric representation,
  - the necessary material, property, type, and relationship entities
    referenced by those elements.
"""

from __future__ import annotations

from pathlib import Path
from typing import Set

import ifcopenshell


def _collect_dependency_graph(
    ifc_file: ifcopenshell.file,
    element_ids: Set[int],
) -> Set[int]:
    """
    Starting from a set of product element ids, recursively traverse every
    attribute reference and collect the full set of entity ids that must be
    copied to make the subset self-contained.  Stops recursion at
    IfcOwnerHistory (we recreate those) and spatial-structure entities
    (IfcProject, IfcSite, IfcBuilding) which are scaffolded separately.
    """
    visited: Set[int] = set()
    spatial_types = {
        "IfcProject", "IfcSite", "IfcBuilding",
        "IfcRelContainedInSpatialStructure", "IfcRelAggregates",
        "IfcRelAssignsToGroup", "IfcDistributionSystem",
        "IfcRelConnectsPorts", "IfcRelConnectsElements",
        "IfcRelNests", "IfcDistributionPort",
    }

    def walk(entity):
        eid = entity.id()
        if eid == 0 or eid in visited:
            return
        if entity.is_a("IfcOwnerHistory"):
            return  # skip — we create a fresh one
        if entity.is_a() in spatial_types:
            return
        visited.add(eid)
        for attr in entity:
            if isinstance(attr, ifcopenshell.entity_instance):
                walk(attr)
            elif isinstance(attr, (tuple, list)):
                for item in attr:
                    if isinstance(item, ifcopenshell.entity_instance):
                        walk(item)

    for eid in element_ids:
        walk(ifc_file.by_id(eid))

    # Also pull in IfcRelDefinesByType / IfcRelAssociatesMaterial that
    # reference any of our elements.
    for rel in ifc_file.by_type("IfcRelDefinesByType"):
        overlap = {o.id() for o in rel.RelatedObjects} & element_ids
        if overlap:
            walk(rel.RelatingType)
    for rel in ifc_file.by_type("IfcRelAssociatesMaterial"):
        overlap = {o.id() for o in rel.RelatedObjects} & element_ids
        if overlap:
            walk(rel)

    return visited


def write_ifc_subset(
    source: ifcopenshell.file,
    element_ids: Set[int],
    output_path: Path,
    model_name: str = "Subset",
) -> Path:
    """
    Write a new IFC4 file containing only the elements whose step-ids are
    in *element_ids*, together with all of their geometric, material, and
    type dependencies.
    """
    deps = _collect_dependency_graph(source, element_ids)

    new = ifcopenshell.file(schema="IFC4")

    # ---- Scaffold: units, project, site, building ---------------------- #
    # Copy unit assignment verbatim
    old_units = source.by_type("IfcUnitAssignment")[0]
    id_map: dict[int, ifcopenshell.entity_instance] = {}

    def deep_copy(entity):
        """Recursively copy an entity and its attribute-level deps."""
        if entity.id() == 0:
            return entity
        if entity.id() in id_map:
            return id_map[entity.id()]
        if entity.is_a("IfcOwnerHistory"):
            # Return a shared owner-history created below
            return owner_history
        new_attrs = []
        for attr in entity:
            if isinstance(attr, ifcopenshell.entity_instance):
                new_attrs.append(deep_copy(attr))
            elif isinstance(attr, (tuple, list)):
                new_items = []
                for item in attr:
                    if isinstance(item, ifcopenshell.entity_instance):
                        new_items.append(deep_copy(item))
                    else:
                        new_items.append(item)
                new_attrs.append(new_items)
            else:
                new_attrs.append(attr)
        new_entity = new.create_entity(entity.is_a(), *new_attrs)
        id_map[entity.id()] = new_entity
        return new_entity

    # Owner history (minimal)
    person = new.create_entity("IfcPerson", "$", "IFCSplitter", "Tool", None, None, None, None, None)
    org = new.create_entity("IfcOrganization", None, "IFCSplitter", None, None, None)
    pao = new.create_entity("IfcPersonAndOrganization", person, org, None)
    app = new.create_entity("IfcApplication", org, "1.0", "IFC Splitter", "IFCSplitter")
    owner_history = new.create_entity(
        "IfcOwnerHistory", pao, app, "READWRITE", "ADDED", 0, pao, app, 0
    )

    units = deep_copy(old_units)

    # Geometric context
    origin = new.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
    zdir = new.create_entity("IfcDirection", (0.0, 0.0, 1.0))
    xdir = new.create_entity("IfcDirection", (1.0, 0.0, 0.0))
    axis = new.create_entity("IfcAxis2Placement3D", origin, zdir, xdir)
    ctx = new.create_entity(
        "IfcGeometricRepresentationContext", None, "Model", 3, 0.0001, axis, None
    )
    sub_ctx = new.create_entity(
        "IfcGeometricRepresentationSubContext",
        "Body", "Model", None, None, None, None, ctx, None, "MODEL_VIEW", None,
    )

    project = new.create_entity(
        "IfcProject",
        ifcopenshell.guid.new(),
        owner_history,
        model_name,
        None, None, None, None, (ctx,), units,
    )

    site_place = new.create_entity("IfcAxis2Placement3D", origin, zdir, xdir)
    site_lp = new.create_entity("IfcLocalPlacement", None, site_place)
    site = new.create_entity(
        "IfcSite",
        ifcopenshell.guid.new(), owner_history, "Site", None, None,
        site_lp, None, None, None, None, None, None, None, None,
    )
    new.create_entity(
        "IfcRelAggregates",
        ifcopenshell.guid.new(), owner_history, None, None, project, (site,),
    )

    bldg_place = new.create_entity("IfcAxis2Placement3D", origin, zdir, xdir)
    bldg_lp = new.create_entity("IfcLocalPlacement", site_lp, bldg_place)
    building = new.create_entity(
        "IfcBuilding",
        ifcopenshell.guid.new(), owner_history, model_name, None, None,
        bldg_lp, None, None, None, None, None, None,
    )
    new.create_entity(
        "IfcRelAggregates",
        ifcopenshell.guid.new(), owner_history, None, None, site, (building,),
    )

    # ---- Remap the sub-context references ------------------------------ #
    # Any IfcGeometricRepresentationSubContext in the source that maps to
    # 'Body'/'Model' should be redirected to our new sub_ctx.
    old_sub_ctxs = set()
    for sc in source.by_type("IfcGeometricRepresentationSubContext"):
        old_sub_ctxs.add(sc.id())
    for sc_id in old_sub_ctxs:
        id_map[sc_id] = sub_ctx
    old_ctx = source.by_type("IfcGeometricRepresentationContext")
    for c in old_ctx:
        if not c.is_a("IfcGeometricRepresentationSubContext"):
            id_map[c.id()] = ctx

    # ---- Copy product elements ----------------------------------------- #
    copied_elements = []
    for eid in element_ids:
        elem = source.by_id(eid)
        new_elem = deep_copy(elem)
        copied_elements.append(new_elem)

    # Also copy remaining dependency entities not yet visited
    for dep_id in deps:
        if dep_id not in id_map:
            deep_copy(source.by_id(dep_id))

    # ---- IfcRelAssociatesMaterial -------------------------------------- #
    for rel in source.by_type("IfcRelAssociatesMaterial"):
        overlap = [
            id_map[o.id()]
            for o in rel.RelatedObjects
            if o.id() in element_ids and o.id() in id_map
        ]
        if overlap:
            mat = deep_copy(rel.RelatingMaterial)
            new.create_entity(
                "IfcRelAssociatesMaterial",
                ifcopenshell.guid.new(), owner_history, None, None,
                overlap, mat,
            )

    # ---- IfcRelDefinesByType ------------------------------------------- #
    for rel in source.by_type("IfcRelDefinesByType"):
        overlap = [
            id_map[o.id()]
            for o in rel.RelatedObjects
            if o.id() in element_ids and o.id() in id_map
        ]
        if overlap:
            rtype = deep_copy(rel.RelatingType)
            new.create_entity(
                "IfcRelDefinesByType",
                ifcopenshell.guid.new(), owner_history, None, None,
                overlap, rtype,
            )

    # ---- Spatial containment ------------------------------------------- #
    if copied_elements:
        new.create_entity(
            "IfcRelContainedInSpatialStructure",
            ifcopenshell.guid.new(), owner_history, None, None,
            copied_elements, building,
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    new.write(str(output_path))
    return output_path