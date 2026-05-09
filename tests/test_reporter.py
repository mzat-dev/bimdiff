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

import csv
import io
import json

from bimdiff import diff_ifc, export_csv, export_html, export_json
from bimdiff.reporter import format_summary_text


def test_export_json_valid(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    output = export_json(result)
    parsed = json.loads(output)
    assert "added" in parsed
    assert "removed" in parsed
    assert "modified" in parsed
    assert "summary" in parsed


def test_export_csv_headers(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    output = export_csv(result)
    reader = csv.reader(io.StringIO(output))
    headers = next(reader)
    assert "status" in headers
    assert "global_id" in headers
    assert "ifc_type" in headers


def test_export_csv_row_count(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    output = export_csv(result)
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    # Header + at least one data row
    assert len(rows) > 1


def test_export_html_contains_summary(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    html = export_html(result)
    assert "BIM Diff Report" in html
    assert "Added" in html
    assert "Removed" in html
    assert "Modified" in html


def test_export_html_footer_uses_installed_version(simple_v1_path, simple_v2_path):
    """The footer must reflect the installed package version, not a stale literal."""
    from bimdiff import __version__

    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    html = export_html(result)
    assert f"BIM Diff v{__version__}" in html


def test_format_summary_text(simple_v1_path, simple_v2_path):
    result = diff_ifc(str(simple_v1_path), str(simple_v2_path))
    text = format_summary_text(result, "v1.ifc", "v2.ifc")
    assert "BIM Diff Report" in text
    assert "v1.ifc" in text
    assert "v2.ifc" in text
    assert "Severity:" in text


def test_export_csv_escapes_formula_injection():
    """CSV cells starting with =, +, -, @, tab or CR must be prefixed with '
    so that Excel/Sheets do not execute them as formulas."""
    from bimdiff.models import (
        CanonicalEntity, DiffResult, DiffSummary, ModifiedEntity, PropertyChange,
    )
    from bimdiff.reporter import export_csv

    result = DiffResult(
        added=[CanonicalEntity(global_id="g1", ifc_type="IfcWall", name="=SUM(A1:A10)")],
        modified=[ModifiedEntity(
            global_id="g2",
            ifc_type="IfcDoor",
            changes=[PropertyChange(
                field="properties.X",
                old_value="@cmd",
                new_value="-2+5",
                change_type="property",
            )],
        )],
        summary=DiffSummary(
            total_added=1, total_removed=0, total_modified=1, total_unchanged=0,
            severity="low",
        ),
    )
    out = export_csv(result)
    assert "'=SUM(A1:A10)" in out
    assert "'@cmd" in out
    assert "'-2+5" in out


def test_extract_entity_normalizes_wrapped_pset_values(simple_v1_path):
    """Wrapped IFC values (e.g. IfcLabel) must be unwrapped before storage,
    otherwise export_json fails on real models with non-primitive psets."""
    import ifcopenshell

    from bimdiff.differ import DiffEngine

    ifc = ifcopenshell.open(str(simple_v1_path))
    engine = DiffEngine(ifc, ifc)
    wall = next(iter(ifc.by_type("IfcWall")))

    class FakeWrapped:
        wrappedValue = "wrapped-string"

    engine._psets_cache[engine._eid(wall)] = {"FakePset": {"FakeProp": FakeWrapped()}}
    entity = engine._extract_entity(wall, ifc)

    assert entity.properties.get("FakePset.FakeProp") == "wrapped-string"
    # And the round-trip through JSON must work
    json.dumps(entity.model_dump(mode="json"))
