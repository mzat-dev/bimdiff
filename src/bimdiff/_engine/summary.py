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

"""Diff summary computation for the diff engine."""

from __future__ import annotations

from collections import Counter

from bimdiff.models import CanonicalEntity, DiffSummary, ModifiedEntity


class SummaryMixin:
    """Computes the final ``DiffSummary`` from added/removed/modified entities."""

    __slots__ = ()

    @staticmethod
    def _compute_summary(
        added: list[CanonicalEntity],
        removed: list[CanonicalEntity],
        modified: list[ModifiedEntity],
        unchanged_count: int,
    ) -> DiffSummary:
        total = len(added) + len(removed) + len(modified) + unchanged_count
        changed = len(added) + len(removed) + len(modified)

        property_changes = geometry_changes = relationship_changes = 0
        for m in modified:
            for c in m.changes:
                if c.change_type == "property":
                    property_changes += 1
                elif c.change_type == "geometry":
                    geometry_changes += 1
                elif c.change_type == "relationship":
                    relationship_changes += 1

        type_counter: Counter[str] = Counter()
        for e in added:
            type_counter[e.ifc_type] += 1
        for e in removed:
            type_counter[e.ifc_type] += 1
        for m in modified:
            type_counter[m.ifc_type] += 1

        storey_counter: Counter[str] = Counter()
        for e in added:
            if e.storey:
                storey_counter[e.storey] += 1
        for e in removed:
            if e.storey:
                storey_counter[e.storey] += 1
        for m in modified:
            if m.storey:
                storey_counter[m.storey] += 1

        if total == 0:
            severity = "low"
        else:
            pct = (changed / total) * 100
            severity = "low" if pct < 5 else "medium" if pct <= 20 else "high"

        return DiffSummary(
            total_added=len(added),
            total_removed=len(removed),
            total_modified=len(modified),
            total_unchanged=unchanged_count,
            property_changes=property_changes,
            geometry_changes=geometry_changes,
            relationship_changes=relationship_changes,
            most_impacted_types=[t for t, _ in type_counter.most_common(3)],
            most_impacted_storeys=[s for s, _ in storey_counter.most_common(3)],
            severity=severity,
        )
