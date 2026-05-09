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

import sys
from pathlib import Path

import click

from bimdiff.differ import diff_ifc
from bimdiff.models import DiffResult
from bimdiff.reporter import export_csv, export_html, export_json, format_summary_text


@click.command()
@click.argument("old_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("new_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format", "output_format",
    type=click.Choice(["text", "json", "csv", "html"]),
    default="text",
    help="Output format (default: text summary).",
)
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file path (default: stdout).",
)
@click.option(
    "--filter-type",
    default=None,
    help="Filter by IFC type(s), comma-separated (e.g. IfcWall,IfcDoor).",
)
@click.option(
    "--filter-storey",
    default=None,
    help="Filter by storey name.",
)
@click.option(
    "--summary-only",
    is_flag=True,
    help="Show only the summary, no element details.",
)
@click.option(
    "--hide-noise",
    is_flag=True,
    help=(
        "Strip common export-noise from the result (ArchiCAD renovation "
        "phase, un-named auto-quantities, geometry Plan↔Body flips). "
        "Modified elements whose only changes are noise are reported as "
        "unchanged."
    ),
)
@click.version_option(package_name="bimdiff")
def main(
    old_file: str,
    new_file: str,
    output_format: str,
    output: str | None,
    filter_type: str | None,
    filter_storey: str | None,
    summary_only: bool,
    hide_noise: bool,
) -> None:
    """Compare two IFC files and report what changed.

    \b
    Examples:
        bimdiff old.ifc new.ifc
        bimdiff old.ifc new.ifc --format json -o diff.json
        bimdiff old.ifc new.ifc --filter-type IfcWall,IfcDoor
        bimdiff old.ifc new.ifc --summary-only
    """
    # Push --filter-type into the engine as a selector — narrows the index at
    # build time and avoids scanning the whole model. --filter-storey stays
    # post-hoc because the ifcopenshell selector syntax for storey-by-name is
    # not stable enough to rely on.
    selector = None
    if filter_type:
        types = [t.strip() for t in filter_type.split(",") if t.strip()]
        selector = ", ".join(types) if types else None

    try:
        result = diff_ifc(old_file, new_file, selector=selector)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Apply remaining post-diff filters (storey only, type already handled above)
    if filter_storey:
        result = _filter_result(result, None, filter_storey)

    if hide_noise:
        from bimdiff.filters import filter_noise
        result = filter_noise(result)

    # Format output
    if summary_only:
        content = format_summary_text(
            result,
            old_filename=Path(old_file).name,
            new_filename=Path(new_file).name,
        )
    elif output_format == "text":
        content = format_summary_text(
            result,
            old_filename=Path(old_file).name,
            new_filename=Path(new_file).name,
        )
    elif output_format == "json":
        content = export_json(result)
    elif output_format == "csv":
        content = export_csv(result)
    elif output_format == "html":
        content = export_html(result)
    else:
        content = format_summary_text(result)

    # Write output
    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Report written to {output}")
    else:
        click.echo(content)


def _filter_result(
    result: DiffResult,
    filter_type: str | None,
    filter_storey: str | None,
) -> DiffResult:
    """Filter a DiffResult by IFC type and/or storey."""
    types = {t.strip() for t in filter_type.split(",")} if filter_type else None
    storey = filter_storey

    added = result.added
    removed = result.removed
    modified = result.modified

    if types:
        added = [e for e in added if e.ifc_type in types]
        removed = [e for e in removed if e.ifc_type in types]
        modified = [m for m in modified if m.ifc_type in types]

    if storey:
        added = [e for e in added if e.storey == storey]
        removed = [e for e in removed if e.storey == storey]
        modified = [m for m in modified if m.storey == storey]

    # Recompute summary
    from bimdiff.differ import DiffEngine

    summary = DiffEngine._compute_summary(
        added, removed, modified, result.unchanged_count
    )

    return DiffResult(
        added=added,
        removed=removed,
        modified=modified,
        unchanged_ids=result.unchanged_ids,
        unchanged_count=result.unchanged_count,
        summary=summary,
    )
