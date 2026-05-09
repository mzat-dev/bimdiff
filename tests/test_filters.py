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

from bimdiff.filters import filter_noise, is_noisy_change
from bimdiff.models import (
    DiffResult,
    DiffSummary,
    ModifiedEntity,
    PropertyChange,
)


def test_is_noisy_change_known_patterns():
    assert is_noisy_change("geometry.presence")
    assert is_noisy_change("properties.AC_Pset_RenovationAndPhasing.Renovation Status")
    assert is_noisy_change("properties.None.NetVolume")
    assert is_noisy_change("properties.None.NetFootprintArea")
    # Corrupted UTF-8 pset name
    assert is_noisy_change("properties.\x8b|RC.NetVolume")


def test_is_noisy_change_real_changes_pass():
    assert not is_noisy_change("ifc_type")
    assert not is_noisy_change("properties.material")
    assert not is_noisy_change("properties.Pset_WallCommon.FireRating")
    assert not is_noisy_change("properties.Pset_ColumnCommon.Reference")
    assert not is_noisy_change("relationships.container")
    assert not is_noisy_change("geometry.bbox_size")


def _make_result(modified_entries):
    """Build a minimal DiffResult with the given ModifiedEntity list."""
    summary = DiffSummary(
        total_added=0,
        total_removed=0,
        total_modified=len(modified_entries),
        total_unchanged=0,
        severity="low",
    )
    return DiffResult(modified=modified_entries, summary=summary)


def _change(field: str) -> PropertyChange:
    return PropertyChange(field=field, change_type="property")


def test_filter_noise_strips_only_noise_changes():
    """A modified entity with mixed real + noisy changes keeps only the
    real ones."""
    m = ModifiedEntity(
        global_id="real-mix",
        ifc_type="IfcWall",
        changes=[
            _change("properties.material"),
            _change("properties.AC_Pset_RenovationAndPhasing.Renovation Status"),
            _change("geometry.presence"),
        ],
    )
    out = filter_noise(_make_result([m]))
    assert len(out.modified) == 1
    assert {c.field for c in out.modified[0].changes} == {"properties.material"}
    assert out.summary.total_modified == 1
    assert out.unchanged_count == 0


def test_filter_noise_demotes_all_noise_to_unchanged():
    """An entity whose changes are all noise becomes unchanged."""
    m = ModifiedEntity(
        global_id="all-noise",
        ifc_type="IfcBeam",
        changes=[
            _change("geometry.presence"),
            _change("properties.None.NetVolume"),
        ],
    )
    out = filter_noise(_make_result([m]))
    assert out.modified == []
    assert "all-noise" in out.unchanged_ids
    assert out.unchanged_count == 1
    assert out.summary.total_modified == 0
    assert out.summary.total_unchanged == 1


def test_filter_noise_does_not_mutate_input():
    """The original DiffResult is untouched."""
    m = ModifiedEntity(
        global_id="x",
        ifc_type="IfcWall",
        changes=[_change("geometry.presence")],
    )
    result = _make_result([m])
    filter_noise(result)
    # Original survives intact
    assert len(result.modified) == 1
    assert len(result.modified[0].changes) == 1
