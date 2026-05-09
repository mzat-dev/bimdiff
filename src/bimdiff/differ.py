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

"""High-performance semantic diff engine for IFC/BIM models."""

from __future__ import annotations

import logging
import os
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.representation
import ifcopenshell.util.unit

from bimdiff._engine import (
    ComparatorsMixin,
    EntityExtractorMixin,
    GeometryMixin,
    IfcCacheMixin,
    SummaryMixin,
)
from bimdiff.models import (
    DiffResult,
    ModifiedEntity,
    PropertyChange,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]

# Soft size limit beyond which we warn (does not block).
_LARGE_FILE_WARN_MB = 200


def _warn_if_large(label: str, path: str) -> None:
    try:
        size_mb = os.path.getsize(path) / 1024 / 1024
    except OSError:
        return
    if size_mb > _LARGE_FILE_WARN_MB:
        logger.warning(
            "%s file is %.1f MB (> %d MB); diff may be slow or memory-heavy",
            label, size_mb, _LARGE_FILE_WARN_MB,
        )


@contextmanager
def _quiet_ifc() -> Iterator[None]:
    """Temporarily raise the ifcopenshell logger threshold to ERROR.

    The original implementation used ``logging.disable(logging.CRITICAL)``,
    which silenced *every* logger in the interpreter — including the
    caller's own logging, Sentry breadcrumbs, etc. We only need to mute
    ifcopenshell's chatty per-element warnings during the hot loop.
    """
    ifc_logger = logging.getLogger("ifcopenshell")
    previous = ifc_logger.level
    ifc_logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        ifc_logger.setLevel(previous)


def diff_ifc(
    old_path: str,
    new_path: str,
    selector: str | None = None,
    *,
    filter_elements: str | None = None,
    on_progress: ProgressCallback | None = None,
    geometry_tolerance: float = 2,
) -> DiffResult:
    """Compare two IFC files and return a semantic diff.

    Args:
        old_path: Path to the original IFC file.
        new_path: Path to the revised IFC file.
        selector: Optional ifcopenshell selector string (e.g.
            ``"IfcWall, IfcDoor"``) restricting the diff to a subset of
            elements. Applied at indexing time — much cheaper than
            post-filtering.
        filter_elements: **Deprecated.** Old name for ``selector``. Will be
            removed in v0.3.
        on_progress: Optional callback invoked as the pipeline advances.
            Receives ``(percent: int, label: str)``.
        geometry_tolerance: Percentage tolerance for bbox dimension comparison.
            E.g. 2 means dimensions within 2% are considered equal. Default 2.
    """
    if filter_elements is not None:
        warnings.warn(
            "diff_ifc(filter_elements=...) is deprecated, use selector=... instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if selector is None:
            selector = filter_elements

    def _progress(pct: int, label: str) -> None:
        if on_progress:
            on_progress(pct, label)

    _warn_if_large("old", old_path)
    _warn_if_large("new", new_path)

    _progress(5, "Parsing old model")
    old = ifcopenshell.open(old_path)
    _progress(15, "Parsing new model")
    new = ifcopenshell.open(new_path)
    _progress(25, "Parsing complete")

    engine = DiffEngine(old, new, filter_elements=selector, geometry_tolerance=geometry_tolerance)
    return engine.diff(on_progress=on_progress)


class DiffEngine(
    IfcCacheMixin,
    GeometryMixin,
    ComparatorsMixin,
    EntityExtractorMixin,
    SummaryMixin,
):
    """High-performance semantic diff engine for IFC models.

    Optimized for large models (50MB+) with:
    - Batch geometry processing (single iterator pass)
    - Cached property/relationship lookups
    - Pre-built element index dicts
    - O(1) modified entity lookups
    - Direct shape comparison (no DeepDiff)
    - Parallel geometry summarization

    The implementation is split across mixins in :mod:`bimdiff._engine`:
    caches, geometry, comparators, entity extraction and summary.
    """

    __slots__ = (
        "old", "new", "filter_elements", "precision", "geometry_tolerance",
        "_unit_scale",
        "_old_geom_settings", "_new_geom_settings",
        "_old_elements", "_new_elements",
        "_psets_cache", "_type_cache", "_container_cache", "_aggregate_cache",
        "_classification_cache", "_material_cache", "_on_progress",
    )

    def __init__(
        self,
        old: ifcopenshell.file,
        new: ifcopenshell.file,
        filter_elements: str | None = None,
        geometry_tolerance: float = 2,
    ):
        self.old = old
        self.new = new
        self.filter_elements = filter_elements
        self.geometry_tolerance = geometry_tolerance
        self.precision = 1e-4
        # Multiply a value-in-model-units by this to get metres. Used to make
        # the geometry tolerance unit-aware (1mm in mm-files, 0.001m in metres).
        try:
            self._unit_scale = ifcopenshell.util.unit.calculate_unit_scale(new)
        except Exception:
            self._unit_scale = 1.0

        # Lazy-init caches
        self._old_geom_settings: ifcopenshell.geom.settings | None = None
        self._new_geom_settings: ifcopenshell.geom.settings | None = None
        self._old_elements: dict[str, Any] | None = None
        self._new_elements: dict[str, Any] | None = None

        # Per-element caches (keyed by (file_pointer, element.id()) tuple —
        # see IfcCacheMixin._eid for why both halves are needed).
        _Key = tuple[int, int]
        self._psets_cache: dict[_Key, dict[str, dict[str, Any]]] = {}
        self._type_cache: dict[_Key, Any] = {}
        self._container_cache: dict[_Key, Any] = {}
        self._aggregate_cache: dict[_Key, Any] = {}
        self._classification_cache: dict[_Key, list[Any]] = {}
        self._material_cache: dict[_Key, str | None] = {}
        self._on_progress: ProgressCallback | None = None

    def _progress(self, pct: int, label: str) -> None:
        if self._on_progress:
            self._on_progress(pct, label)

    def diff(self, on_progress: ProgressCallback | None = None) -> DiffResult:
        self._on_progress = on_progress
        with _quiet_ifc():
            return self._run_diff()

    def _run_diff(self) -> DiffResult:
        self._progress(28, "Collecting elements")
        self.precision = self._get_precision()

        old_index = self._get_elements(self.old)
        new_index = self._get_elements(self.new)

        old_ids = set(old_index.keys())
        new_ids = set(new_index.keys())

        added_ids = new_ids - old_ids
        removed_ids = old_ids - new_ids
        common_ids = old_ids & new_ids

        # --- Batch geometry hashes for added/removed ---
        self._progress(32, "Computing geometry hashes")
        added_elements = [new_index[gid] for gid in added_ids]
        removed_elements = [old_index[gid] for gid in removed_ids]

        # Run both batches in parallel
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_added_geo = pool.submit(self._batch_geometry_hashes, self.new, added_elements)
            future_removed_geo = pool.submit(self._batch_geometry_hashes, self.old, removed_elements)
            added_geo_hashes = future_added_geo.result()
            removed_geo_hashes = future_removed_geo.result()

        # --- Build added/removed entities ---
        # sorted() ensures reproducible output order across runs and machines
        # (set iteration order depends on hash seed, which differs between processes).
        self._progress(38, "Extracting added elements")
        added = [
            self._extract_entity(new_index[gid], self.new, added_geo_hashes.get(gid))
            for gid in sorted(added_ids)
        ]

        self._progress(42, "Extracting removed elements")
        removed = [
            self._extract_entity(old_index[gid], self.old, removed_geo_hashes.get(gid))
            for gid in sorted(removed_ids)
        ]

        # --- Diff common elements ---
        self._progress(45, "Comparing properties")
        modified_dict: dict[str, ModifiedEntity] = {}
        unchanged_ids: list[str] = []
        geometry_queue_old: list[Any] = []
        geometry_queue_new: list[Any] = []
        geometry_queue_gids: list[str] = []

        total_common = max(len(common_ids), 1)
        report_interval = max(total_common // 10, 1)

        # sorted() for deterministic iteration; geometry_queue_gids inherits this order.
        for idx, gid in enumerate(sorted(common_ids)):
            if idx % report_interval == 0:
                pct = 45 + int((idx / total_common) * 25)
                self._progress(pct, f"Comparing elements ({idx}/{total_common})")

            old_el = old_index[gid]
            new_el = new_index[gid]

            changes: list[PropertyChange] = []
            changes.extend(self._diff_attributes(old_el, new_el))
            changes.extend(self._diff_properties(old_el, new_el))
            changes.extend(self._diff_relationships(old_el, new_el))

            # Queue geometry for batch processing
            has_body = ifcopenshell.util.representation.get_representation(new_el, "Model", "Body")
            if has_body:
                geometry_queue_old.append(old_el)
                geometry_queue_new.append(new_el)
                geometry_queue_gids.append(gid)

            if changes:
                container = self._get_container(new_el)
                mod_storey = container.Name if container and container.is_a("IfcBuildingStorey") else None
                modified_dict[gid] = ModifiedEntity.model_construct(
                    global_id=gid,
                    ifc_type=new_el.is_a(),
                    name=getattr(new_el, "Name", None),
                    storey=mod_storey,
                    changes=changes,
                )
            elif not has_body:
                unchanged_ids.append(gid)

        # --- Batch geometry diff (parallel old vs new) ---
        self._progress(72, "Computing geometry")
        if geometry_queue_old:
            total_geo = len(geometry_queue_old)
            geo_done = [0, 0]  # [old_done, new_done]
            geo_lock = threading.Lock()
            report_every = max(total_geo // 10, 1)

            def geo_tick(which: int) -> None:
                with geo_lock:
                    geo_done[which] += 1
                    done_total = geo_done[0] + geo_done[1]
                    if done_total % report_every != 0:
                        return
                    expected = total_geo * 2
                    pct = 72 + int((done_total / expected) * 16)
                    self._progress(pct, f"Computing geometry ({done_total}/{expected})")

            with ThreadPoolExecutor(max_workers=2) as pool:
                future_old_shapes = pool.submit(
                    self._summarise_shapes, self.old, geometry_queue_old,
                    lambda: geo_tick(0),
                )
                future_new_shapes = pool.submit(
                    self._summarise_shapes, self.new, geometry_queue_new,
                    lambda: geo_tick(1),
                )
                old_shapes = future_old_shapes.result()
                new_shapes = future_new_shapes.result()

            self._progress(88, "Comparing geometry results")
            for gid in geometry_queue_gids:
                old_shape = old_shapes.get(gid)
                new_shape = new_shapes.get(gid)
                geo_changes = self._shape_changes(old_shape, new_shape)

                if geo_changes:
                    existing = modified_dict.get(gid)
                    if existing:
                        existing.changes.extend(geo_changes)
                    else:
                        el = new_index[gid]
                        container = self._get_container(el)
                        geo_storey = container.Name if container and container.is_a("IfcBuildingStorey") else None
                        modified_dict[gid] = ModifiedEntity.model_construct(
                            global_id=gid,
                            ifc_type=el.is_a(),
                            name=getattr(el, "Name", None),
                            storey=geo_storey,
                            changes=list(geo_changes),
                        )
                elif gid not in modified_dict:
                    unchanged_ids.append(gid)

        self._progress(90, "Generating report")
        modified = list(modified_dict.values())
        unchanged_ids.sort()  # deterministic, paired with sorted iteration above
        summary = self._compute_summary(added, removed, modified, len(unchanged_ids))

        return DiffResult(
            added=added,
            removed=removed,
            modified=modified,
            unchanged_ids=unchanged_ids,
            unchanged_count=len(unchanged_ids),
            summary=summary,
        )
