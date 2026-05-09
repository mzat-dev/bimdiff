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

import logging
from unittest.mock import patch

from bimdiff import diff_ifc
from bimdiff.models import DiffResult


def test_diff_identical_files(identical_path):
    result = diff_ifc(str(identical_path), str(identical_path))
    assert isinstance(result, DiffResult)
    assert len(result.added) == 0
    assert len(result.removed) == 0
    assert len(result.modified) == 0
    assert result.unchanged_count > 0


def test_diff_detects_added(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    added_ids = {e.global_id for e in result.added}
    assert "wall-004-guid-gggg" in added_ids


def test_diff_detects_removed(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    removed_ids = {e.global_id for e in result.removed}
    assert "wall-003-guid-cccc" in removed_ids


def test_diff_detects_modified_property(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    door_mod = next((m for m in result.modified if m.global_id == "door-001-guid-dddd"), None)
    assert door_mod is not None
    fire_change = next((c for c in door_mod.changes if "FireRating" in c.field), None)
    assert fire_change is not None
    assert fire_change.old_value == "EI 30"
    assert fire_change.new_value == "EI 120"


def test_diff_name_change_alone_is_not_modified(simple_v1_path, simple_v2_path):
    """Name-only changes are excluded from diff (IFC names contain volatile IDs)."""
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    slab_mod = next((m for m in result.modified if m.global_id == "slab-001-guid-ffff"), None)
    # slab-001 only had a Name change, so it should NOT be in modified
    assert slab_mod is None


def test_diff_unchanged_elements(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    # wall-001, wall-002, door-002 should be unchanged
    assert result.unchanged_count >= 3
    # unchanged_ids must mirror unchanged_count exactly (they are the same
    # set of elements, just count vs membership-list).
    assert len(result.unchanged_ids) == result.unchanged_count
    assert "wall-001-guid-aaaa" in result.unchanged_ids
    assert "wall-002-guid-bbbb" in result.unchanged_ids
    assert "door-002-guid-eeee" in result.unchanged_ids


def test_diff_summary_counts(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    s = result.summary
    assert s.total_added == len(result.added)
    assert s.total_removed == len(result.removed)
    assert s.total_modified == len(result.modified)
    assert s.total_unchanged == result.unchanged_count


def test_diff_severity_is_valid(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    assert result.summary.severity in ("low", "medium", "high")


def test_diff_empty_old(empty_path, simple_v1_path):
    """Empty old file -> building elements in new are 'added'."""
    result = diff_ifc(str(empty_path), str(simple_v1_path))
    added_types = {e.ifc_type for e in result.added}
    # Should contain actual building elements
    assert added_types & {"IfcWall", "IfcDoor", "IfcSlab"}


def test_diff_empty_new(simple_v1_path, empty_path):
    """Empty new file -> building elements in old are 'removed'."""
    result = diff_ifc(str(simple_v1_path), str(empty_path))
    removed_types = {e.ifc_type for e in result.removed}
    assert removed_types & {"IfcWall", "IfcDoor", "IfcSlab"}


def test_diff_canonical_entity_fields(simple_v1_path, simple_v2_path):
    """Added/removed entities should have populated fields."""
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    for entity in result.added:
        assert entity.global_id
        assert entity.ifc_type


def test_diff_empty_vs_empty(empty_path):
    """Diffing two empty files produces zero changes."""
    result = diff_ifc(str(empty_path), str(empty_path))
    assert len(result.added) == 0
    assert len(result.removed) == 0
    assert len(result.modified) == 0
    assert result.summary.severity == "low"


def test_modified_entity_has_storey(simple_v1_path, simple_v2_path):
    """Modified entities should have storey populated."""
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    storeys = [m.storey for m in result.modified if m.storey is not None]
    assert len(storeys) > 0


def test_modified_storey_in_summary(simple_v1_path, simple_v2_path):
    """most_impacted_storeys should include storeys from modified entities."""
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    mod_storeys = {m.storey for m in result.modified if m.storey}
    if mod_storeys:
        assert any(s in result.summary.most_impacted_storeys for s in mod_storeys)


def test_geometry_hash_failure_returns_empty(simple_v1_path):
    """When geometry iterator raises, _batch_geometry_hashes returns partial results."""
    import ifcopenshell
    from bimdiff.differ import DiffEngine

    old = ifcopenshell.open(str(simple_v1_path))
    engine = DiffEngine(old, old)
    elements = list(old.by_type("IfcWall"))

    with patch("ifcopenshell.geom.iterator", side_effect=RuntimeError("fail")):
        result = engine._batch_geometry_hashes(old, elements)
    assert isinstance(result, dict)


def test_diff_ifc_filter_elements_emits_deprecation_warning(simple_v1_path, simple_v2_path):
    """The legacy filter_elements kwarg still works but warns."""
    import warnings as _w
    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        diff_ifc(str(simple_v1_path), str(simple_v2_path), filter_elements="IfcWall")
    assert any(
        issubclass(w.category, DeprecationWarning)
        and "filter_elements" in str(w.message)
        for w in caught
    )


def test_diff_detects_ifc_type_change():
    """An element keeping the same GlobalId while changing IfcType (e.g.
    IfcWall -> IfcBeam after a Revit family swap) must be flagged."""
    import ifcopenshell
    import ifcopenshell.api

    from bimdiff.differ import DiffEngine

    def _build(ifc_class: str):
        ifc = ifcopenshell.file(schema="IFC4")
        ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
        ifcopenshell.api.run("unit.assign_unit", ifc)
        site = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcSite", name="S")
        bldg = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBuilding", name="B")
        st = ifcopenshell.api.run(
            "root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="L1"
        )
        proj = ifc.by_type("IfcProject")[0]
        ifcopenshell.api.run("aggregate.assign_object", ifc, products=[site], relating_object=proj)
        ifcopenshell.api.run("aggregate.assign_object", ifc, products=[bldg], relating_object=site)
        ifcopenshell.api.run("aggregate.assign_object", ifc, products=[st], relating_object=bldg)
        el = ifcopenshell.api.run("root.create_entity", ifc, ifc_class=ifc_class, name="X")
        ifcopenshell.api.run(
            "attribute.edit_attributes", ifc, product=el,
            attributes={"GlobalId": "type-change-aaaaaaaaa"},
        )
        ifcopenshell.api.run("spatial.assign_container", ifc, products=[el], relating_structure=st)
        return ifc

    old = _build("IfcWall")
    new = _build("IfcBeam")
    result = DiffEngine(old, new).diff()

    target = next(
        (m for m in result.modified if m.global_id == "type-change-aaaaaaaaa"),
        None,
    )
    assert target is not None
    fields = {c.field for c in target.changes}
    assert "ifc_type" in fields, f"missing ifc_type in {fields}"
    change = next(c for c in target.changes if c.field == "ifc_type")
    assert change.old_value == "IfcWall"
    assert change.new_value == "IfcBeam"


def test_shape_changes_unit_aware_in_metres():
    """In a file authored in metres, a 1m delta on a 4m wall must yield a
    geometry.bbox_size change.

    Before unit-aware tolerance, the hardcoded 50-model-unit absolute floor
    silently ignored *any* delta below 50 — which in a metres file means
    50 m, catastrophic.
    """
    import ifcopenshell
    import ifcopenshell.api

    from bimdiff.differ import DiffEngine

    ifc = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "METERS"})

    engine = DiffEngine(ifc, ifc)

    s_old = {"bbox_size": (3.0, 0.3, 2.5), "openings": [], "projections": []}
    s_new = {"bbox_size": (4.0, 0.3, 2.5), "openings": [], "projections": []}
    fields = {c.field for c in engine._shape_changes(s_old, s_new)}
    assert "geometry.bbox_size" in fields


def test_shape_changes_ignores_subprecision_in_mm():
    """Sub-precision shifts (~1mm on a 3000mm wall) must stay noise after the
    unit-aware threshold replaces the hardcoded 50.
    """
    import ifcopenshell
    import ifcopenshell.api

    from bimdiff.differ import DiffEngine

    ifc = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.assign_unit", ifc)  # default millimetres

    engine = DiffEngine(ifc, ifc)

    s_old = {"bbox_size": (3000.0, 300.0, 2500.0), "openings": [], "projections": []}
    s_new = {"bbox_size": (3000.5, 300.0, 2500.0), "openings": [], "projections": []}
    assert engine._shape_changes(s_old, s_new) == []


def test_shape_changes_reports_openings_and_projections():
    """Granular reporting must surface openings and projections as separate
    PropertyChange entries (not collapsed into a single opaque 'geometry')."""
    import ifcopenshell
    import ifcopenshell.api

    from bimdiff.differ import DiffEngine

    ifc = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.assign_unit", ifc)
    engine = DiffEngine(ifc, ifc)

    s_old = {
        "bbox_size": (3000.0, 300.0, 2500.0),
        "openings": ["op-A"],
        "projections": [],
    }
    s_new = {
        "bbox_size": (3000.0, 300.0, 2500.0),  # no bbox change
        "openings": ["op-A", "op-B"],           # opening added
        "projections": ["proj-X"],               # projection added
    }
    changes = engine._shape_changes(s_old, s_new)
    fields = {c.field for c in changes}
    assert "geometry.openings" in fields
    assert "geometry.projections" in fields
    assert "geometry.bbox_size" not in fields  # unchanged

    op_change = next(c for c in changes if c.field == "geometry.openings")
    assert op_change.old_value == ["op-A"]
    assert op_change.new_value == ["op-A", "op-B"]


def test_shape_changes_geometry_presence_xor():
    """If geometry is present on only one side, emit a single
    geometry.presence change."""
    import ifcopenshell
    import ifcopenshell.api

    from bimdiff.differ import DiffEngine

    ifc = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.assign_unit", ifc)
    engine = DiffEngine(ifc, ifc)

    s = {"bbox_size": (1.0, 1.0, 1.0), "openings": [], "projections": []}

    # acquired
    changes = engine._shape_changes(None, s)
    assert len(changes) == 1
    assert changes[0].field == "geometry.presence"
    assert changes[0].old_value == "absent"
    assert changes[0].new_value == "present"

    # lost
    changes = engine._shape_changes(s, None)
    assert len(changes) == 1
    assert changes[0].old_value == "present"
    assert changes[0].new_value == "absent"


def test_summarise_shapes_failure_returns_empty(simple_v1_path):
    """When geometry iterator raises, _summarise_shapes returns partial results."""
    import ifcopenshell
    from bimdiff.differ import DiffEngine

    old = ifcopenshell.open(str(simple_v1_path))
    engine = DiffEngine(old, old)
    elements = list(old.by_type("IfcWall"))

    with patch("ifcopenshell.geom.iterator", side_effect=RuntimeError("fail")):
        result = engine._summarise_shapes(old, elements)
    assert isinstance(result, dict)


def test_diff_output_is_sorted_by_global_id(simple_v1_path, simple_v2_path):
    """Output lists must be sorted by global_id for reproducible diffs/exports."""
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    added_ids = [e.global_id for e in result.added]
    removed_ids = [e.global_id for e in result.removed]
    modified_ids = [m.global_id for m in result.modified]
    assert added_ids == sorted(added_ids)
    assert removed_ids == sorted(removed_ids)
    assert modified_ids == sorted(modified_ids)


def test_diff_flags_added_property(added_props_v1_path, added_props_v2_path):
    """A property present only in v2 must be flagged with old_value=None."""
    result = diff_ifc(str(added_props_v1_path), str(added_props_v2_path))
    target = next(
        (m for m in result.modified if m.global_id == "wall-prop-001-aaaaa"),
        None,
    )
    assert target is not None
    field = "properties.Pset_WallExtra.ThermalTransmittance"
    change = next((c for c in target.changes if c.field == field), None)
    assert change is not None, f"missing {field} in {[c.field for c in target.changes]}"
    assert change.old_value is None
    assert change.new_value == 0.25


def test_diff_flags_removed_property(added_props_v2_path, added_props_v1_path):
    """A property present only in v1 (now removed) must surface with new_value=None."""
    # Reverse direction: v2 (with property) -> v1 (without)
    result = diff_ifc(str(added_props_v2_path), str(added_props_v1_path))
    target = next(
        (m for m in result.modified if m.global_id == "wall-prop-001-aaaaa"),
        None,
    )
    assert target is not None
    field = "properties.Pset_WallExtra.ThermalTransmittance"
    change = next((c for c in target.changes if c.field == field), None)
    assert change is not None
    assert change.old_value == 0.25
    assert change.new_value is None


def test_diff_detects_material_change(material_v1_path, material_v2_path):
    """Material changes (CLS 25 -> CLS 30) must be flagged as PropertyChange."""
    result = diff_ifc(str(material_v1_path), str(material_v2_path))
    target = next(
        (m for m in result.modified if m.global_id == "wall-mat-001-aaaaaa"),
        None,
    )
    assert target is not None, "wall-mat-001-aaaaaa should appear in modified"
    fields = {c.field for c in target.changes}
    assert "properties.material" in fields, f"material change missing in {fields}"
    mat_change = next(c for c in target.changes if c.field == "properties.material")
    assert mat_change.old_value == "CLS 25"
    assert mat_change.new_value == "CLS 30"


def test_duplicate_global_id_emits_warning(duplicate_guid_path, caplog):
    """When two elements share a GlobalId, _build_element_index keeps the first
    and emits a WARNING — and the warning survives the diff pipeline now that
    logging is silenced selectively (only ifcopenshell)."""
    with caplog.at_level(logging.WARNING, logger="bimdiff._engine.caches"):
        diff_ifc(str(duplicate_guid_path), str(duplicate_guid_path))

    assert any(
        "Duplicate GlobalId" in r.message and "0duplicateXXXXXXXXXXXX" in r.message
        for r in caplog.records
    )


def test_diff_does_not_silence_user_logging(simple_v1_path, simple_v2_path, caplog):
    """Replacement for the old logging.disable(CRITICAL) approach: user
    loggers must keep emitting through diff_ifc."""
    user_logger = logging.getLogger("test_user_logger_marker")
    with caplog.at_level(logging.INFO, logger="test_user_logger_marker"):
        user_logger.info("before-diff-marker")
        diff_ifc(str(simple_v1_path), str(simple_v2_path))
        user_logger.info("after-diff-marker")

    msgs = {r.message for r in caplog.records}
    assert "before-diff-marker" in msgs
    assert "after-diff-marker" in msgs
