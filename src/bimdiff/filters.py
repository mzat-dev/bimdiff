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

"""Optional output filters for ``DiffResult``.

The diff engine itself stays neutral and reports every change it can detect.
Some real-world IFC pipelines (notably ArchiCAD exports) re-stamp a handful
of housekeeping properties on every save, which drowns the actual semantic
diff in noise. This module surfaces that noise as an explicit, opt-in filter
that callers can apply to the engine output before rendering.
"""

from __future__ import annotations

from bimdiff.models import DiffResult, ModifiedEntity

# Exact field names that are always export-noise.
_NOISE_FIELDS: frozenset[str] = frozenset({
    # IfcRepresentation Plan vs Body export: the model is the same, the
    # exporter just chose to emit a 2D symbol on one side and a 3D body on
    # the other. Visually identical in any 3D viewer.
    "geometry.presence",
})

# Field prefixes that capture whole pset families known to be ephemeral.
_NOISE_FIELD_PREFIXES: tuple[str, ...] = (
    # ArchiCAD stamps the renovation phase on every element on every save.
    "properties.AC_Pset_RenovationAndPhasing.",
    # IfcElementQuantity entries that the exporter emits without a pset
    # name end up under "None" — these are auto-derived geometry quantities
    # (NetVolume, NetFootprintArea, ...) that flicker between exports.
    "properties.None.",
)


def is_noisy_change(field: str) -> bool:
    """Return True if ``field`` matches a known export-noise pattern.

    Patterns covered:

    - exact ``geometry.presence`` (Plan ↔ Body export flips)
    - ``properties.AC_Pset_RenovationAndPhasing.*`` (ArchiCAD phase stamp)
    - ``properties.None.*`` (un-named auto-derived quantities)
    - any ``properties.<pset>.*`` whose ``<pset>`` segment contains
      non-printable or non-ASCII bytes (typically corrupted UTF-8 from
      exporters that emit project-internal label names)
    """
    if field in _NOISE_FIELDS:
        return True
    if any(field.startswith(p) for p in _NOISE_FIELD_PREFIXES):
        return True
    parts = field.split(".")
    if len(parts) >= 2 and parts[0] == "properties":
        pset = parts[1]
        if any(ord(c) > 126 or ord(c) < 32 for c in pset):
            return True
    return False


def filter_noise(result: DiffResult) -> DiffResult:
    """Return a new ``DiffResult`` with noisy changes stripped.

    Each ``ModifiedEntity`` is rebuilt with only its non-noise changes; if
    the resulting change list is empty, the entity is demoted to unchanged
    (its GlobalId moves to ``unchanged_ids``). Counts and severity are
    recomputed accordingly.

    The original ``result`` is not mutated.
    """
    # Local import keeps the public ``bimdiff.filters`` import path free of
    # the heavy ifcopenshell side-effects that ``differ`` carries.
    from bimdiff.differ import DiffEngine

    new_modified: list[ModifiedEntity] = []
    demoted_to_unchanged: list[str] = []
    for m in result.modified:
        kept = [c for c in m.changes if not is_noisy_change(c.field)]
        if kept:
            new_modified.append(ModifiedEntity.model_construct(
                global_id=m.global_id,
                ifc_type=m.ifc_type,
                name=m.name,
                storey=m.storey,
                changes=kept,
            ))
        else:
            demoted_to_unchanged.append(m.global_id)

    new_unchanged_ids = sorted(result.unchanged_ids + demoted_to_unchanged)
    summary = DiffEngine._compute_summary(
        result.added, result.removed, new_modified, len(new_unchanged_ids),
    )
    return DiffResult(
        added=result.added,
        removed=result.removed,
        modified=new_modified,
        unchanged_ids=new_unchanged_ids,
        unchanged_count=len(new_unchanged_ids),
        summary=summary,
    )
