# bimdiff - Semantic diff engine for IFC/BIM models
# Copyright (C) 2026 BIM Diff contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-FileCopyrightText: 2026 BIM Diff contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Generate IFC test fixtures using IfcOpenShell.

Run: python tests/fixtures/generate_fixtures.py

Creates:
  - simple_v1.ifc / simple_v2.ifc: 6 elements with known diffs
  - identical.ifc: for testing 0 changes
  - empty.ifc: valid IFC with no building elements
"""

from pathlib import Path

import ifcopenshell
import ifcopenshell.api

FIXTURES_DIR = Path(__file__).parent


def _setup_project(ifc: ifcopenshell.file) -> tuple:
    """Create project, site, building, and storey."""
    project = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="TestProject")
    # Set units
    ifcopenshell.api.run("unit.assign_unit", ifc)
    # Create spatial hierarchy
    site = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSite", name="TestSite")
    building = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuilding", name="TestBuilding")
    storey1 = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="Level 1")
    storey2 = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="Level 2")

    ifcopenshell.api.run("aggregate.assign_object", ifc, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", ifc, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", ifc, products=[storey1, storey2], relating_object=building)

    return project, site, building, storey1, storey2


def _create_wall(
    ifc: ifcopenshell.file,
    storey: ifcopenshell.entity_instance,
    global_id: str,
    name: str,
    fire_rating: str = "REI 60",
    is_external: bool = True,
    material: str | None = None,
    extra_props: dict | None = None,
) -> ifcopenshell.entity_instance:
    wall = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcWall", name=name)
    ifcopenshell.api.run("attribute.edit_attributes", ifc, product=wall, attributes={"GlobalId": global_id})
    ifcopenshell.api.run("spatial.assign_container", ifc, products=[wall], relating_structure=storey)

    pset = ifcopenshell.api.run("pset.add_pset", ifc, product=wall, name="Pset_WallCommon")
    ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties={
        "FireRating": fire_rating,
        "IsExternal": is_external,
        "LoadBearing": True,
    })

    if material:
        mat = ifcopenshell.api.run("material.add_material", ifc, name=material, category="concrete")
        ifcopenshell.api.run("material.assign_material", ifc, products=[wall], type="IfcMaterial", material=mat)

    if extra_props:
        pset_extra = ifcopenshell.api.run("pset.add_pset", ifc, product=wall, name="Pset_WallExtra")
        ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset_extra, properties=extra_props)

    return wall


def _create_door(
    ifc: ifcopenshell.file,
    storey: ifcopenshell.entity_instance,
    global_id: str,
    name: str,
    fire_rating: str = "EI 30",
) -> ifcopenshell.entity_instance:
    door = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcDoor", name=name)
    ifcopenshell.api.run("attribute.edit_attributes", ifc, product=door, attributes={"GlobalId": global_id})
    ifcopenshell.api.run("spatial.assign_container", ifc, products=[door], relating_structure=storey)

    pset = ifcopenshell.api.run("pset.add_pset", ifc, product=door, name="Pset_DoorCommon")
    ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties={
        "FireRating": fire_rating,
        "IsExternal": False,
    })
    return door


def _create_slab(
    ifc: ifcopenshell.file,
    storey: ifcopenshell.entity_instance,
    global_id: str,
    name: str,
) -> ifcopenshell.entity_instance:
    slab = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSlab", name=name)
    ifcopenshell.api.run("attribute.edit_attributes", ifc, product=slab, attributes={"GlobalId": global_id})
    ifcopenshell.api.run("spatial.assign_container", ifc, products=[slab], relating_structure=storey)
    return slab


def create_simple_v1():
    """Create v1 with 6 elements:
    - wall-001, wall-002, wall-003 on Level 1
    - door-001, door-002 on Level 1
    - slab-001 on Level 1
    """
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, storey2 = _setup_project(ifc)

    _create_wall(ifc, storey1, "wall-001-guid-aaaa", "External Wall A", fire_rating="REI 60")
    _create_wall(ifc, storey1, "wall-002-guid-bbbb", "External Wall B", fire_rating="REI 60")
    _create_wall(ifc, storey1, "wall-003-guid-cccc", "Internal Wall C", fire_rating="REI 30", is_external=False)
    _create_door(ifc, storey1, "door-001-guid-dddd", "Door Main", fire_rating="EI 30")
    _create_door(ifc, storey1, "door-002-guid-eeee", "Door Service", fire_rating="EI 30")
    _create_slab(ifc, storey1, "slab-001-guid-ffff", "Floor Slab P1")

    ifc.write(str(FIXTURES_DIR / "simple_v1.ifc"))
    print(f"Created simple_v1.ifc ({len(ifc.by_type('IfcElement'))} elements)")


def create_simple_v2():
    """Create v2 with known changes vs v1:
    - wall-001: UNCHANGED
    - wall-002: UNCHANGED
    - wall-003: REMOVED
    - wall-004: ADDED on Level 2
    - door-001: MODIFIED (FireRating EI 30 -> EI 120)
    - door-002: UNCHANGED
    - slab-001: MODIFIED (name changed)
    """
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, storey2 = _setup_project(ifc)

    _create_wall(ifc, storey1, "wall-001-guid-aaaa", "External Wall A", fire_rating="REI 60")
    _create_wall(ifc, storey1, "wall-002-guid-bbbb", "External Wall B", fire_rating="REI 60")
    # wall-003 removed
    _create_wall(ifc, storey2, "wall-004-guid-gggg", "New Wall Level 2", fire_rating="REI 90")
    _create_door(ifc, storey1, "door-001-guid-dddd", "Door Main", fire_rating="EI 120")  # changed
    _create_door(ifc, storey1, "door-002-guid-eeee", "Door Service", fire_rating="EI 30")
    _create_slab(ifc, storey1, "slab-001-guid-ffff", "Floor Slab P1 - Revised")  # name changed

    ifc.write(str(FIXTURES_DIR / "simple_v2.ifc"))
    print(f"Created simple_v2.ifc ({len(ifc.by_type('IfcElement'))} elements)")


def create_identical():
    """Create a model for testing 0 changes."""
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)

    _create_wall(ifc, storey1, "wall-id-001-aaaa", "Wall A")
    _create_door(ifc, storey1, "door-id-001-bbbb", "Door A")

    ifc.write(str(FIXTURES_DIR / "identical.ifc"))
    print(f"Created identical.ifc ({len(ifc.by_type('IfcElement'))} elements)")


def create_empty():
    """Create a valid IFC with project structure but no elements."""
    ifc = ifcopenshell.file(schema="IFC4")
    _setup_project(ifc)
    ifc.write(str(FIXTURES_DIR / "empty.ifc"))
    print("Created empty.ifc (0 elements)")


def create_material_v1():
    """v1 with one wall, material 'CLS 25'."""
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)
    _create_wall(ifc, storey1, "wall-mat-001-aaaaaa", "Concrete Wall", material="CLS 25")
    ifc.write(str(FIXTURES_DIR / "material_v1.ifc"))
    print("Created material_v1.ifc (wall with material CLS 25)")


def create_material_v2():
    """v2 with same wall (same GUID), material upgraded to 'CLS 30'."""
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)
    _create_wall(ifc, storey1, "wall-mat-001-aaaaaa", "Concrete Wall", material="CLS 30")
    ifc.write(str(FIXTURES_DIR / "material_v2.ifc"))
    print("Created material_v2.ifc (wall with material CLS 30)")


def create_added_props_v1():
    """v1: wall without Pset_WallExtra (will be added in v2)."""
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)
    _create_wall(ifc, storey1, "wall-prop-001-aaaaa", "Themal Wall")
    ifc.write(str(FIXTURES_DIR / "added_props_v1.ifc"))
    print("Created added_props_v1.ifc (wall without Pset_WallExtra)")


def create_added_props_v2():
    """v2: same wall (same GUID) with Pset_WallExtra.ThermalTransmittance added."""
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)
    _create_wall(
        ifc,
        storey1,
        "wall-prop-001-aaaaa",
        "Themal Wall",
        extra_props={"ThermalTransmittance": 0.25},
    )
    ifc.write(str(FIXTURES_DIR / "added_props_v2.ifc"))
    print("Created added_props_v2.ifc (wall with Pset_WallExtra.ThermalTransmittance=0.25)")


def create_duplicate_guid():
    """Create a file with two walls sharing the same GlobalId.

    Useful to test that the diff engine logs a warning instead of silently
    overwriting elements when a source file has GUID collisions (rare but
    happens with bad exporters or post-processing scripts).
    """
    ifc = ifcopenshell.file(schema="IFC4")
    _, _, _, storey1, _ = _setup_project(ifc)

    # Create with placeholder GUIDs (ifcopenshell.api would reject duplicates),
    # then force the collision via direct attribute mutation.
    w1 = _create_wall(ifc, storey1, "0placeholder1aaaaaaaaa", "First Wall")
    w2 = _create_wall(ifc, storey1, "0placeholder2bbbbbbbbb", "Second Wall")

    duplicate_guid = "0duplicateXXXXXXXXXXXX"
    w1.GlobalId = duplicate_guid
    w2.GlobalId = duplicate_guid

    ifc.write(str(FIXTURES_DIR / "duplicate_guid.ifc"))
    print(f"Created duplicate_guid.ifc (2 walls share GUID {duplicate_guid})")


if __name__ == "__main__":
    create_simple_v1()
    create_simple_v2()
    create_identical()
    create_empty()
    create_duplicate_guid()
    create_material_v1()
    create_material_v2()
    create_added_props_v1()
    create_added_props_v2()
    print("All fixtures generated.")
