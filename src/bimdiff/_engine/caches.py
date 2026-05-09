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

"""Cached IFC lookups and element index for the diff engine."""

from __future__ import annotations

import logging
from typing import Any

import ifcopenshell
import ifcopenshell.util.classification
import ifcopenshell.util.element
import ifcopenshell.util.selector

logger = logging.getLogger(__name__)


class IfcCacheMixin:
    """Per-element cached lookups + element index builder.

    Mixed into ``DiffEngine``; relies on ``self.old``, ``self.new``,
    ``self.filter_elements`` and the cache dicts initialized in ``__init__``.
    """

    __slots__ = ()

    @staticmethod
    def _eid(element: Any) -> tuple[int, int]:
        """Composite cache key uniquely identifying an element across files.

        ``element.id()`` alone collides when old and new files happen to assign
        the same integer id to different elements (common, since IFC ids are
        positional). Pairing with the file pointer disambiguates them.
        """
        return (element.wrapped_data.file_pointer(), element.id())

    def _get_psets(self, element: Any) -> dict[str, dict[str, Any]]:
        eid = self._eid(element)
        if eid not in self._psets_cache:
            self._psets_cache[eid] = ifcopenshell.util.element.get_psets(element)
        return self._psets_cache[eid]

    def _get_type(self, element: Any) -> Any:
        eid = self._eid(element)
        if eid not in self._type_cache:
            self._type_cache[eid] = ifcopenshell.util.element.get_type(element)
        return self._type_cache[eid]

    def _get_container(self, element: Any) -> Any:
        eid = self._eid(element)
        if eid not in self._container_cache:
            self._container_cache[eid] = ifcopenshell.util.element.get_container(element)
        return self._container_cache[eid]

    def _get_aggregate(self, element: Any) -> Any:
        eid = self._eid(element)
        if eid not in self._aggregate_cache:
            self._aggregate_cache[eid] = ifcopenshell.util.element.get_aggregate(element)
        return self._aggregate_cache[eid]

    def _get_classification_refs(self, element: Any) -> list[Any]:
        eid = self._eid(element)
        if eid not in self._classification_cache:
            try:
                self._classification_cache[eid] = list(
                    ifcopenshell.util.classification.get_references(element)
                )
            except Exception:
                self._classification_cache[eid] = []
        return self._classification_cache[eid]

    def _get_material_string(self, element: Any) -> str | None:
        """Cached, normalized representation of an element's material assignment.

        Returns a single string regardless of whether the IFC uses IfcMaterial,
        IfcMaterialLayerSet, IfcMaterialList, or related variants — so it can
        be compared verbatim across two file revisions.
        """
        eid = self._eid(element)
        if eid not in self._material_cache:
            material = ifcopenshell.util.element.get_material(element)
            self._material_cache[eid] = self._material_to_string(material)
        return self._material_cache[eid]

    @staticmethod
    def _material_to_string(material: Any) -> str | None:
        if material is None:
            return None
        if material.is_a("IfcMaterial"):
            return material.Name
        if hasattr(material, "MaterialLayers"):
            return ", ".join(
                layer.Material.Name for layer in material.MaterialLayers if layer.Material
            )
        if hasattr(material, "Materials"):
            return ", ".join(m.Name for m in material.Materials if m)
        return str(material.is_a())

    def _get_elements(self, ifc: ifcopenshell.file) -> dict[str, Any]:
        """Build a {GlobalId: element} dict for all diffable elements."""
        if ifc is self.old:
            if self._old_elements is None:
                self._old_elements = self._build_element_index(ifc)
            return self._old_elements
        if self._new_elements is None:
            self._new_elements = self._build_element_index(ifc)
        return self._new_elements

    def _build_element_index(self, ifc: ifcopenshell.file) -> dict[str, Any]:
        if self.filter_elements:
            elements = ifcopenshell.util.selector.filter_elements(ifc, self.filter_elements)
        else:
            elements = list(ifc.by_type("IfcElement"))
            if ifc.schema == "IFC2X3":
                elements += list(ifc.by_type("IfcSpatialStructureElement"))
            else:
                elements += list(ifc.by_type("IfcSpatialElement"))
        # First-wins on collisions: keeps order deterministic and lets us
        # surface the bad data via a warning instead of silently dropping.
        index: dict[str, Any] = {}
        for e in elements:
            if e.is_a("IfcFeatureElement"):
                continue
            if e.GlobalId in index:
                logger.warning(
                    "Duplicate GlobalId %s in schema %s (keeping #%d, dropping #%d)",
                    e.GlobalId, ifc.schema, index[e.GlobalId].id(), e.id(),
                )
                continue
            index[e.GlobalId] = e
        return index
