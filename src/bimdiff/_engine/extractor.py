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

"""CanonicalEntity extraction for the diff engine."""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.util.element

from bimdiff._engine.comparators import ComparatorsMixin
from bimdiff.models import CanonicalEntity


class EntityExtractorMixin:
    """Builds ``CanonicalEntity`` from raw IFC elements.

    Uses cached lookups from ``IfcCacheMixin`` via ``self``.
    """

    __slots__ = ()

    def _extract_entity(
        self,
        element: Any,
        ifc: ifcopenshell.file,
        geometry_hash: str | None = None,
    ) -> CanonicalEntity:
        container = self._get_container(element)
        storey = container.Name if container and container.is_a("IfcBuildingStorey") else None

        psets = self._get_psets(element)
        properties: dict[str, Any] = {}
        for pset_name, pset_props in psets.items():
            for prop_name, prop_value in pset_props.items():
                if prop_name == "id":
                    continue
                # Normalize so wrapped IFC values (IfcLabel, IfcMeasure, etc.)
                # become JSON-serializable primitives — required by export_json.
                properties[f"{pset_name}.{prop_name}"] = ComparatorsMixin._normalize_value(prop_value)

        # Reuse the same cached helper that _diff_properties consumes, so
        # display value and diff value never disagree.
        material_str = self._get_material_string(element)
        if material_str:
            properties["Material"] = material_str

        relationships: dict[str, str] = {}
        if container:
            relationships["containment"] = container.Name or container.is_a()
        type_el = self._get_type(element)
        if type_el:
            relationships["type"] = type_el.Name or type_el.GlobalId

        refs = self._get_classification_refs(element)
        if refs:
            id_attr = "ItemReference" if ifc.schema == "IFC2X3" else "Identification"
            properties["Classification"] = ", ".join(
                getattr(r, id_attr, str(r)) for r in refs
            )

        return CanonicalEntity.model_construct(
            global_id=element.GlobalId,
            ifc_type=element.is_a(),
            name=getattr(element, "Name", None),
            storey=storey,
            properties=properties,
            geometry_hash=geometry_hash,
            relationships=relationships,
        )
