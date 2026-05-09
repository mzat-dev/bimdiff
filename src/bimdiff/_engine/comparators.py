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

"""Attribute / property / relationship diffing for the diff engine."""

from __future__ import annotations

from typing import Any

from bimdiff.models import PropertyChange


class ComparatorsMixin:
    """Field-level comparison logic for ``DiffEngine``.

    Uses the cached lookups provided by ``IfcCacheMixin`` and ``self.old``,
    ``self.new`` from the host class.
    """

    __slots__ = ()

    @staticmethod
    def _diff_attributes(old: Any, new: Any) -> list[PropertyChange]:
        # Name, Description, ObjectType are excluded: they often contain
        # volatile Revit IDs or differ between export settings.
        # The IFC class itself is not volatile — a wall becoming a beam
        # while keeping the same GlobalId is a real, important change.
        changes: list[PropertyChange] = []
        old_class = old.is_a()
        new_class = new.is_a()
        if old_class != new_class:
            changes.append(PropertyChange.model_construct(
                field="ifc_type",
                old_value=old_class,
                new_value=new_class,
                change_type="property",
            ))
        return changes

    def _diff_properties(self, old: Any, new: Any) -> list[PropertyChange]:
        changes: list[PropertyChange] = []
        old_flat = self._flatten_psets(self._get_psets(old))
        new_flat = self._flatten_psets(self._get_psets(new))

        # Material is associated via IfcRelAssociatesMaterial, not via psets.
        # Inject it into the same flat dict so it goes through the same diff
        # logic — without this, material changes are silently ignored.
        old_mat = self._get_material_string(old)
        new_mat = self._get_material_string(new)
        if old_mat is not None or new_mat is not None:
            old_flat["material"] = old_mat
            new_flat["material"] = new_mat

        # Compare the union of keys: a property added or removed between
        # revisions is itself a change (None -> value or value -> None).
        all_keys = old_flat.keys() | new_flat.keys()
        for key in all_keys:
            old_val = old_flat.get(key)
            new_val = new_flat.get(key)
            if old_val != new_val:
                changes.append(PropertyChange.model_construct(
                    field=f"properties.{key}",
                    old_value=old_val,
                    new_value=new_val,
                    change_type="property",
                ))
        return changes

    @staticmethod
    def _normalize_value(val: Any) -> Any:
        """Convert IFC entity objects to comparable primitives."""
        if val is None or isinstance(val, (str, int, bool)):
            return val
        if isinstance(val, float):
            return round(val, 5)
        if hasattr(val, "wrappedValue"):
            v = val.wrappedValue
            return round(v, 5) if isinstance(v, float) else v
        if hasattr(val, "is_a"):
            return str(val)
        if isinstance(val, (list, tuple)):
            return [ComparatorsMixin._normalize_value(v) for v in val]
        return val

    # Property sets to skip entirely during comparison
    _SKIP_PSETS = frozenset({"AC_Pset_Name"})

    @staticmethod
    def _flatten_psets(psets: dict[str, dict[str, Any]]) -> dict[str, Any]:
        flat: dict[str, Any] = {}
        for pset_name, props in psets.items():
            if pset_name in ComparatorsMixin._SKIP_PSETS:
                continue
            for prop_name, prop_value in props.items():
                if prop_name != "id":
                    flat[f"{pset_name}.{prop_name}"] = ComparatorsMixin._normalize_value(prop_value)
        return flat

    @staticmethod
    def _changed(old_val: Any, new_val: Any) -> bool:
        """True only when both values exist and differ (ignores None↔value)."""
        if old_val is None or new_val is None:
            return False
        return old_val != new_val

    def _diff_relationships(self, old: Any, new: Any) -> list[PropertyChange]:
        changes: list[PropertyChange] = []

        # relationships.type excluded: Revit type names contain volatile IDs

        old_container = self._get_container(old)
        new_container = self._get_container(new)
        old_cont = old_container.Name if old_container else None
        new_cont = new_container.Name if new_container else None
        if self._changed(old_cont, new_cont):
            changes.append(PropertyChange.model_construct(
                field="relationships.container",
                old_value=old_cont, new_value=new_cont, change_type="relationship",
            ))

        old_agg = self._get_aggregate(old)
        new_agg = self._get_aggregate(new)
        old_agg_name = getattr(old_agg, "Name", None) if old_agg else None
        new_agg_name = getattr(new_agg, "Name", None) if new_agg else None
        if self._changed(old_agg_name, new_agg_name):
            changes.append(PropertyChange.model_construct(
                field="relationships.aggregate",
                old_value=old_agg_name, new_value=new_agg_name, change_type="relationship",
            ))

        old_id_attr = "ItemReference" if self.old.schema == "IFC2X3" else "Identification"
        new_id_attr = "ItemReference" if self.new.schema == "IFC2X3" else "Identification"
        old_refs = sorted(
            getattr(r, old_id_attr, str(r))
            for r in self._get_classification_refs(old)
        )
        new_refs = sorted(
            getattr(r, new_id_attr, str(r))
            for r in self._get_classification_refs(new)
        )
        if old_refs != new_refs and old_refs and new_refs:
            changes.append(PropertyChange.model_construct(
                field="relationships.classification",
                old_value=", ".join(old_refs) if old_refs else None,
                new_value=", ".join(new_refs) if new_refs else None,
                change_type="relationship",
            ))

        return changes
