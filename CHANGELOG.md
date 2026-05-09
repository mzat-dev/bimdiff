# Changelog

All notable changes to `bimdiff` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] — 2026-04-18

Adds an opt-in noise filter for real-world IFC pipelines (notably ArchiCAD)
that re-stamp housekeeping properties on every save and drown the actual
semantic diff in noise.

### Added

- **`bimdiff.filters` module** with two helpers:
  - `is_noisy_change(field) -> bool` — predicate for known noise patterns:
    `geometry.presence` (Plan ↔ Body export flips),
    `properties.AC_Pset_RenovationAndPhasing.*` (ArchiCAD phase stamp),
    `properties.None.*` (un-named auto-derived quantities), and
    pset names containing non-printable / non-ASCII bytes (corrupted
    UTF-8 from exporters that emit project-internal label names).
  - `filter_noise(DiffResult) -> DiffResult` — strips noisy
    `PropertyChange` entries; modified entities whose changes are *all*
    noise are demoted to unchanged. Counts and severity are recomputed.
- **CLI: `--hide-noise` flag** that routes the diff result through
  `filter_noise` before rendering. On the typical ArchiCAD round-trip
  this drops 30–60% of the modified count by removing pure export noise.

The diff engine itself stays neutral and keeps reporting every change it
can detect — filtering is purely opt-in post-processing.

## [0.2.1] — 2026-04-18

Hardening release. No behaviour changes for normal diffs; security and
operational improvements.

### Security

- **CSV export now escapes formula injection.** Cells starting with
  `=`, `+`, `-`, `@`, tab or CR are prefixed with an apostrophe so that
  Excel and Google Sheets do not execute them as formulas. Closes a
  realistic attack surface for shared review CSVs.

### Fixed

- **`logging.disable(logging.CRITICAL)` no longer silences user logging.**
  The hot-loop logging suppression is replaced by a `_quiet_ifc` context
  manager that only raises the `ifcopenshell` logger to ERROR. User
  loggers, Sentry breadcrumbs and `bimdiff._engine.*` warnings (such as
  the duplicate-`GlobalId` notice) keep emitting.

### Added

- **Soft warning when an input IFC exceeds 200 MB.** Non-blocking, but
  leaves a breadcrumb in the user's logs when a slow/heavy diff is
  expected.
- **PyPI metadata.** `classifiers` and `keywords` are now set so the
  package is discoverable when searching for "ifc", "bim", "diff".
- **`ifcopenshell` is pinned to `>=0.8,<0.9`** to match the API surface
  the engine is tested against.

### Changed

- **HTML report footer renders the installed package version.** Previously
  hardcoded as `v0.1.0` and drifting with every release. `__version__`
  now reads from `importlib.metadata`, making `pyproject.toml` the
  single source of truth.

## [0.2.0] — 2026-04-12

Minor release adding completeness to the diff and a couple of API tweaks.
Output schemas evolve in additive ways, but the change-count totals in
``DiffSummary`` will look different on the same input — see *Breaking* below.

### Added

- **Property additions and removals between revisions are now flagged.**
  `_diff_properties` previously only compared the intersection of pset keys; a
  new `Pset_WallCommon.ThermalTransmittance` in v2 was silently ignored.
  The diff now compares the union and emits `None → value` /
  `value → None` `PropertyChange` entries.
- **IFC type changes with a stable `GlobalId` are now detected.** When an
  element flips from `IfcWall` to `IfcBeam` while keeping the same GUID
  (Revit family swap, etc.), a `PropertyChange(field="ifc_type", ...)` is
  emitted.
- **`DiffResult.unchanged_ids: list[str]`.** Web viewers and downstream
  tools needed the GlobalIds of unchanged elements to colour them
  appropriately. Sorted for reproducibility. `unchanged_count` is kept
  alongside as a denormalized counter.
- **Granular geometry change reporting.** `_shapes_differ` (single bool) is
  replaced by `_shape_changes` (list of `PropertyChange`). Geometry diffs
  now surface as up to three categories:
  `geometry.bbox_size`, `geometry.openings`, `geometry.projections`. If
  geometry is present on only one side, a single `geometry.presence`
  change is emitted (`"absent"` / `"present"`).
- **`diff_ifc(selector=...)`** as the canonical name for the
  ifcopenshell-selector argument. The old `filter_elements` keyword still
  works but emits a `DeprecationWarning`; it will be removed in v0.3.

### Changed

- **CLI `--filter-type` now narrows the diff at the engine level.** It is
  converted to an ifcopenshell selector and passed via `selector=...`,
  avoiding the previous full-diff-then-filter round-trip. `--filter-storey`
  remains post-hoc.

### Breaking

- `DiffSummary.geometry_changes` can grow up to ~3× because each affected
  element may now contribute multiple granular changes instead of one
  opaque entry.
- Elements that previously appeared as `unchanged` may now appear as
  `modified` when the only difference is a property added or removed
  (rather than a value change). `unchanged_count` adjusts accordingly.

## [0.1.2] — 2026-04-04

### Fixed

- **Geometry tolerance is now unit-aware.** `_shapes_differ` previously used a
  hardcoded 50-model-unit absolute floor below which all shape deltas were
  ignored. In a file authored in metres that meant a 50-metre delta was
  silently swallowed; in millimetres it was the intended ~5 cm noise floor.
  The threshold is now derived from
  `ifcopenshell.util.unit.calculate_unit_scale(...)` and the IFC's declared
  precision, so 1 mm of physical noise stays noise regardless of the file's
  authored length unit.

## [0.1.1] — 2026-03-29

### Fixed

- **Material changes are now detected.** Previously, a wall changing from `CLS 25`
  to `CLS 30` was silently treated as unchanged because `_diff_properties` only
  looked at property sets, while materials are associated via
  `IfcRelAssociatesMaterial`. The material is now extracted via a cached helper
  and routed through the same diff path as psets.
- **Element caches no longer collide between old and new files.** `IfcCacheMixin`
  keyed every entry by `element.id()` alone, but IFC ids are positional integers
  that frequently overlap between two revisions of the same model. Entries are
  now keyed by `(file_pointer, element.id())`, eliminating false negatives in
  property/relationship/material diffs that previously passed only by coincidence.
- **`CanonicalEntity.properties` is now JSON-serializable.** Wrapped IFC values
  (`IfcLabel`, `IfcPositiveLengthMeasure`, etc.) leaked from `get_psets()` into
  the canonical entity, causing `export_json(result)` to fail on real Revit
  exports. Values are now normalized at extraction time.
- **Diff output is deterministic across runs.** Set iterations in
  `differ.py` produced output whose order depended on `PYTHONHASHSEED`, breaking
  reproducible CSV/JSON exports and report-hash diffing. `added`, `removed` and
  `modified` are now sorted by `global_id`.
- **Duplicate `GlobalId`s in source files emit a warning instead of silently
  overwriting.** `_build_element_index` switches to first-wins semantics and
  logs a `WARNING` for each collision, surfacing bad exporter output.

### Docs

- Added a "Known Limitations" section to `README.md` covering property
  add/remove blindness, undetected `IfcType` swaps, opaque geometry change
  reporting, and unit-aware tolerance — each with the milestone where it will
  be addressed.

## [0.1.0] — 2026-03-21

Initial public release.
