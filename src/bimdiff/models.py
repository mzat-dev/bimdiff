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

from typing import Any

from pydantic import BaseModel, Field


class CanonicalEntity(BaseModel):
    """Normalized representation of a single IFC element."""

    global_id: str
    ifc_type: str
    name: str | None = None
    storey: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    geometry_hash: str | None = None
    relationships: dict[str, str] = Field(default_factory=dict)


class PropertyChange(BaseModel):
    """A single changed field between old and new version of an entity."""

    field: str
    old_value: Any = None
    new_value: Any = None
    change_type: str  # "property" | "geometry" | "relationship"


class ModifiedEntity(BaseModel):
    """An entity present in both old and new, with differences."""

    global_id: str
    ifc_type: str
    name: str | None = None
    storey: str | None = None
    changes: list[PropertyChange] = Field(default_factory=list)


class DiffSummary(BaseModel):
    """Aggregate statistics about the diff."""

    total_added: int
    total_removed: int
    total_modified: int
    total_unchanged: int
    property_changes: int = 0
    geometry_changes: int = 0
    relationship_changes: int = 0
    most_impacted_types: list[str] = Field(default_factory=list)
    most_impacted_storeys: list[str] = Field(default_factory=list)
    severity: str  # "low" | "medium" | "high"


class DiffResult(BaseModel):
    """Complete result of comparing two IFC files."""

    added: list[CanonicalEntity] = Field(default_factory=list)
    removed: list[CanonicalEntity] = Field(default_factory=list)
    modified: list[ModifiedEntity] = Field(default_factory=list)
    # GlobalIds of elements present in both files with no detected change.
    # Needed by 3D viewers to colour the unchanged geometry without re-deriving
    # the set on the client. ``unchanged_count`` is kept as a denormalized
    # counter for back-compat with v0.1.x.
    unchanged_ids: list[str] = Field(default_factory=list)
    unchanged_count: int = 0
    summary: DiffSummary
