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

"""Geometry settings, batch hashing and shape summarization for the diff engine."""

from __future__ import annotations

import hashlib
import logging
import multiprocessing
from typing import Any

import ifcopenshell
import ifcopenshell.geom

from bimdiff.models import PropertyChange

logger = logging.getLogger(__name__)

_CPU_COUNT = max(multiprocessing.cpu_count(), 1)


class GeometryMixin:
    """Geometry-related operations for ``DiffEngine``.

    Relies on ``self.old``, ``self.new``, ``self._old_geom_settings`` and
    ``self._new_geom_settings`` from the host class.
    """

    __slots__ = ()

    def _get_geom_settings(self, ifc: ifcopenshell.file) -> ifcopenshell.geom.settings:
        if ifc is self.old:
            if self._old_geom_settings is None:
                self._old_geom_settings = self._build_geom_settings(ifc)
            return self._old_geom_settings
        if self._new_geom_settings is None:
            self._new_geom_settings = self._build_geom_settings(ifc)
        return self._new_geom_settings

    @staticmethod
    def _build_geom_settings(ifc: ifcopenshell.file) -> ifcopenshell.geom.settings:
        settings = ifcopenshell.geom.settings()
        settings.set("disable-boolean-result", True)
        settings.set("disable-opening-subtractions", True)
        body_contexts = [
            c.id()
            for c in ifc.by_type("IfcGeometricRepresentationSubContext")
            if c.ContextIdentifier in ("Body", "Facetation")
        ]
        body_contexts.extend(
            c.id()
            for c in ifc.by_type("IfcGeometricRepresentationContext", include_subtypes=False)
            if c.ContextType == "Model"
        )
        if body_contexts:
            settings.set("context-ids", body_contexts)
        return settings

    def _batch_geometry_hashes(
        self, ifc: ifcopenshell.file, elements: list[Any]
    ) -> dict[str, str]:
        if not elements:
            return {}
        hashes: dict[str, str] = {}
        try:
            settings = self._get_geom_settings(ifc)
            iterator = ifcopenshell.geom.iterator(
                settings, ifc, _CPU_COUNT, include=elements
            )
            if not iterator.initialize():
                return hashes
            while True:
                shape = iterator.get()
                el = ifc.by_id(shape.id)
                verts = shape.geometry.verts
                if verts:
                    rounded = [round(v, 3) for v in verts]
                    xs, ys, zs = rounded[0::3], rounded[1::3], rounded[2::3]
                    bbox_str = f"{min(xs)},{min(ys)},{min(zs)},{max(xs)},{max(ys)},{max(zs)}"
                    hashes[el.GlobalId] = hashlib.sha256(bbox_str.encode()).hexdigest()[:16]
                if not iterator.next():
                    break
        except Exception:
            logger.warning("Geometry hashing failed for %d elements", len(elements), exc_info=True)
        return hashes

    def _summarise_shapes(
        self, ifc: ifcopenshell.file, elements: list[Any],
        on_element: Any = None,
    ) -> dict[str, dict[str, Any]]:
        shapes: dict[str, dict[str, Any]] = {}
        if not elements:
            return shapes
        try:
            settings = self._get_geom_settings(ifc)
            iterator = ifcopenshell.geom.iterator(
                settings, ifc, _CPU_COUNT, include=elements
            )
            if not iterator.initialize():
                return shapes
            while True:
                shape = iterator.get()
                element = ifc.by_id(shape.id)
                verts = list(shape.geometry.verts)
                m = list(shape.transformation.matrix)
                if verts and m:
                    # Transform vertices to world-space
                    xs, ys, zs = [], [], []
                    for i in range(0, len(verts), 3):
                        x, y, z = verts[i], verts[i + 1], verts[i + 2]
                        xs.append(m[0] * x + m[3] * y + m[6] * z + m[9])
                        ys.append(m[1] * x + m[4] * y + m[7] * z + m[10])
                        zs.append(m[2] * x + m[5] * y + m[8] * z + m[11])
                    # Compare dimensions (sorted to handle rotations)
                    # Round to 2 decimal places to eliminate tessellation noise
                    size = sorted([
                        round(max(xs) - min(xs), 2),
                        round(max(ys) - min(ys), 2),
                        round(max(zs) - min(zs), 2),
                    ])
                    bbox_size = (size[0], size[1], size[2])
                    shapes[element.GlobalId] = {
                        "bbox_size": bbox_size,
                        "openings": sorted(
                            o.RelatedOpeningElement.GlobalId
                            for o in (getattr(element, "HasOpenings", None) or [])
                        ),
                        "projections": sorted(
                            o.RelatedFeatureElement.GlobalId
                            for o in (getattr(element, "HasProjections", None) or [])
                        ),
                    }
                if on_element:
                    on_element()
                if not iterator.next():
                    break
        except Exception:
            logger.warning("Geometry summarization failed for %d elements", len(elements), exc_info=True)
        return shapes

    def _shape_changes(
        self, old_shape: dict | None, new_shape: dict | None
    ) -> list[PropertyChange]:
        """Compare two shape summaries and return granular geometry changes.

        Up to three categories are surfaced as separate PropertyChange entries:

        - ``geometry.bbox_size`` — bounding box dimensions changed beyond
          tolerance (unit-aware, see _shapes_differ docstring of v0.1.2 for
          how the threshold is derived).
        - ``geometry.openings`` — the set of associated IfcOpeningElements
          (windows, doors cut into a wall) changed.
        - ``geometry.projections`` — the set of associated projections
          (sills, soffits) changed.

        If geometry is present on only one side, a single
        ``geometry.presence`` change is emitted with values ``"absent"`` /
        ``"present"``.
        """
        changes: list[PropertyChange] = []

        # Geometry lost or acquired (XOR on presence)
        if (old_shape is None) != (new_shape is None):
            changes.append(PropertyChange.model_construct(
                field="geometry.presence",
                old_value="absent" if old_shape is None else "present",
                new_value="absent" if new_shape is None else "present",
                change_type="geometry",
            ))
            return changes

        if old_shape is None and new_shape is None:
            return changes

        old_size = old_shape["bbox_size"]
        new_size = new_shape["bbox_size"]
        tol = self.geometry_tolerance / 100.0
        # 0.001 m / unit_scale = "1 mm" expressed in the file's model units.
        abs_threshold = max(self.precision * 10, 0.001 / self._unit_scale)
        bbox_changed = False
        for a, b in zip(old_size, new_size):
            diff = abs(a - b)
            if diff <= abs_threshold:
                continue
            ref = max(abs(a), abs(b), 1e-6)
            if diff / ref > tol:
                bbox_changed = True
                break
        if bbox_changed:
            changes.append(PropertyChange.model_construct(
                field="geometry.bbox_size",
                old_value=list(old_size),
                new_value=list(new_size),
                change_type="geometry",
            ))

        if old_shape["openings"] != new_shape["openings"]:
            changes.append(PropertyChange.model_construct(
                field="geometry.openings",
                old_value=list(old_shape["openings"]),
                new_value=list(new_shape["openings"]),
                change_type="geometry",
            ))

        if old_shape["projections"] != new_shape["projections"]:
            changes.append(PropertyChange.model_construct(
                field="geometry.projections",
                old_value=list(old_shape["projections"]),
                new_value=list(new_shape["projections"]),
                change_type="geometry",
            ))

        return changes

    def _get_precision(self) -> float:
        contexts = [
            c for c in self.new.by_type("IfcGeometricRepresentationContext")
            if c.ContextType == "Model"
        ]
        return contexts[0].Precision if contexts and contexts[0].Precision else 1e-4
