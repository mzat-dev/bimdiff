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

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from bimdiff.models import DiffResult


_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Characters that, at the start of a CSV cell, trigger formula execution
# in Excel / Google Sheets (CSV injection / Formula Injection).
_CSV_INJECTION_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(val: Any) -> str:
    """Stringify a value and prefix with a leading apostrophe if it could be
    interpreted as a spreadsheet formula."""
    s = "" if val is None else str(val)
    if s and s[0] in _CSV_INJECTION_CHARS:
        return "'" + s
    return s


def export_json(result: DiffResult) -> str:
    """Serialize DiffResult to a JSON string."""
    return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False)


def export_csv(result: DiffResult) -> str:
    """Export diff as CSV string.

    One row per changed entity. For modified entities, one row per PropertyChange.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "status", "global_id", "ifc_type", "name", "storey",
        "field_changed", "old_value", "new_value", "change_type",
    ])

    def row(*cells: Any) -> None:
        writer.writerow([_safe_cell(c) for c in cells])

    for entity in result.added:
        row(
            "added", entity.global_id, entity.ifc_type,
            entity.name or "", entity.storey or "",
            "", "", "", "",
        )

    for entity in result.removed:
        row(
            "removed", entity.global_id, entity.ifc_type,
            entity.name or "", entity.storey or "",
            "", "", "", "",
        )

    for entity in result.modified:
        if not entity.changes:
            row(
                "modified", entity.global_id, entity.ifc_type,
                entity.name or "", "",
                "", "", "", "",
            )
        else:
            for change in entity.changes:
                row(
                    "modified", entity.global_id, entity.ifc_type,
                    entity.name or "", "",
                    change.field, change.old_value, change.new_value,
                    change.change_type,
                )

    return output.getvalue()


def export_html(result: DiffResult) -> str:
    """Render diff as standalone HTML report using Jinja2."""
    # Local import avoids a circular import at module load time
    # (bimdiff/__init__.py imports reporter.export_html).
    from bimdiff import __version__

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(result=result, summary=result.summary, version=__version__)


def format_summary_text(
    result: DiffResult,
    old_filename: str = "old.ifc",
    new_filename: str = "new.ifc",
) -> str:
    """Format the summary as human-readable plain text for CLI output."""
    s = result.summary
    old_count = s.total_removed + s.total_modified + s.total_unchanged
    new_count = s.total_added + s.total_modified + s.total_unchanged

    lines = [
        "BIM Diff Report",
        "=" * 15,
        f"Old: {old_filename} ({old_count:,} elements)",
        f"New: {new_filename} ({new_count:,} elements)",
        "",
        "Summary",
        "-" * 7,
        f"  Added:     {s.total_added:,} elements",
        f"  Removed:   {s.total_removed:,} elements",
        f"  Modified:  {s.total_modified:,} elements",
        f"  Unchanged: {s.total_unchanged:,} elements",
        f"  Severity:  {s.severity.upper()}",
        "",
        f"  Property changes:     {s.property_changes:,}",
        f"  Geometry changes:     {s.geometry_changes:,}",
        f"  Relationship changes: {s.relationship_changes:,}",
    ]

    if s.most_impacted_types:
        types_str = ", ".join(s.most_impacted_types)
        lines.append(f"\nMost impacted types: {types_str}")

    if s.most_impacted_storeys:
        storeys_str = ", ".join(s.most_impacted_storeys)
        lines.append(f"Most impacted floors: {storeys_str}")

    return "\n".join(lines) + "\n"
