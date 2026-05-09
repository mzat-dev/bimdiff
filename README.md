# 🏗️ BIM Diff

[![PyPI version](https://img.shields.io/pypi/v/bimdiff.svg)](https://pypi.org/project/bimdiff/)
[![Python](https://img.shields.io/pypi/pyversions/bimdiff.svg)](https://pypi.org/project/bimdiff/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/mzat-dev/bimdiff)

> Semantic diff engine for IFC/BIM models. See exactly what changed between two revisions, in seconds.

BIM Diff is a Python library and CLI that compares two IFC files and produces a structured, element-level report of everything that was added, removed, or modified. It understands the shape of a building model (properties, materials, classifications, geometry, spatial relationships) instead of treating IFC as plain text. If you review BIM revisions for a living, or you ship a platform that needs to answer "what's different?", this is the engine you can plug in.

Built for BIM coordinators, design reviewers, QA engineers, and platform teams who are tired of eyeballing model revisions.

## 🌐 Try It Online

The hosted web app at **[bimdiff.net](https://bimdiff.net/)** gives you a 3D viewer, interactive filtering, and shareable reports without installing anything. Free during the public beta. The core engine in this repo will always stay open source under AGPL-3.0.

<a href="https://bimdiff.net/">
  <img src="https://img.shields.io/badge/Try%20it%20online-bimdiff.net-2ea44f?style=for-the-badge&logo=buildkite&logoColor=white" alt="Try bimdiff.net" />
</a>

---

## ✨ Features

- **GlobalId matching.** Elements are tracked across revisions by their stable IFC `GlobalId`, so a renamed wall stays the same wall.
- **Property-level diffs.** Detects changes in property sets (`Pset_*`), materials, classifications, and standard attributes (`Name`, `Description`, `ObjectType`).
- **Geometry diffs.** Bounding box hashing plus a per-element shape summary (vertex count, vertex sum, min/max bounds, transform, openings, projections) catches real shape changes while ignoring noise.
- **Relationship diffs.** Flags changes in type assignment, spatial containment (which storey), aggregation, and classification references.
- **Severity scoring.** Automatic low / medium / high rating based on the percentage of affected elements.
- **Multiple export formats.** Structured JSON, flat CSV, standalone HTML report, and a human-readable text summary.
- **Runtime filters.** Narrow down by IFC type (`IfcWall,IfcDoor`) or by storey name, both from the CLI and the API.
- **Progress callbacks.** Hook into the diff pipeline to drive a progress bar in your own UI.
- **Performance-focused.** Batch geometry processing, cached lookups, parallel shape summarization, direct shape comparison without `DeepDiff` overhead.
- **Schema-aware.** Handles IFC2x3 and IFC4+ transparently, including the differences in classification and spatial structure.
- **Typed API.** Fully annotated Pydantic v2 models, no guessing what comes back.

## 📦 Installation

```bash
pip install bimdiff
```

Requirements:

- Python 3.10 or newer
- `ifcopenshell` is pulled in automatically. On Windows and macOS you may need the official wheels from the [ifcopenshell releases](https://github.com/IfcOpenShell/IfcOpenShell) if `pip` cannot find a prebuilt package.

Want to hack on the engine itself?

```bash
git clone https://github.com/mzat-dev/bimdiff.git
cd bimdiff
pip install -e ".[dev]"
pytest
```

## 🚀 Quick Start

### Python API

```python
from bimdiff import diff_ifc, export_html, export_json, filter_noise

def on_progress(pct: int, label: str) -> None:
    print(f"[{pct:3d}%] {label}")

result = diff_ifc("model_v1.ifc", "model_v2.ifc", on_progress=on_progress)

# Optional: strip ArchiCAD-style export noise (renovation phase stamps,
# auto-derived quantities, geometry presence flips). Returns a fresh
# DiffResult; modified entities whose changes were entirely noise are
# demoted to unchanged.
result = filter_noise(result)

print(f"Added:    {result.summary.total_added}")
print(f"Removed:  {result.summary.total_removed}")
print(f"Modified: {result.summary.total_modified}")
print(f"Severity: {result.summary.severity.upper()}")
print(f"Most impacted types: {', '.join(result.summary.most_impacted_types)}")

with open("report.html", "w", encoding="utf-8") as f:
    f.write(export_html(result))

with open("diff.json", "w", encoding="utf-8") as f:
    f.write(export_json(result))
```

### CLI

```bash
# Human-readable summary printed to stdout
bimdiff old.ifc new.ifc

# Structured JSON for your pipeline
bimdiff old.ifc new.ifc --format json -o diff.json

# Standalone HTML report you can share with the review team
bimdiff old.ifc new.ifc --format html -o report.html

# Flat CSV you can open in Excel or Google Sheets
bimdiff old.ifc new.ifc --format csv -o changes.csv

# Narrow down to specific IFC types
bimdiff old.ifc new.ifc --filter-type IfcWall,IfcDoor

# Or to a specific storey
bimdiff old.ifc new.ifc --filter-storey "Level 2"

# Only the aggregated summary, no element details
bimdiff old.ifc new.ifc --summary-only

# Strip common export noise (ArchiCAD renovation phase, auto-quantities,
# geometry Plan↔Body flips). Modified elements whose only changes are
# noise are reported as unchanged.
bimdiff old.ifc new.ifc --hide-noise
```

### Output example

```
BIM Diff Report
===============
Old: model_v1.ifc (2,847 elements)
New: model_v2.ifc (2,920 elements)

Summary
-------
  Added:     73 elements
  Removed:   12 elements
  Modified:  109 elements
  Unchanged: 2,726 elements
  Severity:  MEDIUM

  Property changes:     87
  Geometry changes:     14
  Relationship changes: 8

Most impacted types:   IfcWall, IfcDoor, IfcWindow
Most impacted storeys: Level 2, Level 1, Level 3
```

## 🧠 How It Works

BIM Diff runs a four-stage pipeline on each pair of files:

1. **Parse.** `ifcopenshell` loads the file and walks every `IfcElement` plus the spatial structure (`IfcSpatialStructureElement` in IFC2x3, `IfcSpatialElement` in IFC4+). `IfcFeatureElement` subtypes (openings, projections) are intentionally excluded: they are compared via their host element's shape summary instead.
2. **Canonicalize.** Each element is converted to a `CanonicalEntity`: `GlobalId`, `ifc_type`, `name`, `storey`, flattened properties in `PSetName.PropName` form, relationships (containment, type, aggregate, classification), and a SHA256-16 bounding-box hash. Materials and classifications are extracted through the schema-aware helpers in `ifcopenshell.util`.
3. **Match by GlobalId.** Two O(1) dictionaries are built (old and new). Missing IDs on one side are added or removed. Common IDs become candidates for a per-field comparison.
4. **Diff.** For every common pair the engine compares attributes, properties, relationships, and (in a second pass) geometry shape summaries. Geometry summaries are produced by the `ifcopenshell.geom` iterator in parallel (two threads) with boolean operations disabled to keep things fast. Results are rolled up into a `DiffResult` with a severity score and top-impacted types / storeys.

Design choices worth knowing:

- **Bounding box hashing first, shape summary second.** Cheap elements are ruled out in microseconds; only candidates that survive the hash check go through the more expensive vertex comparison.
- **Tolerance is driven by the IFC file's own precision.** If the model declares 1e-5, BIM Diff respects it. Default fallback is 1e-4.
- **No `DeepDiff`.** A custom `_shapes_differ()` comparison avoids the overhead of reflection-based tools on large payloads.
- **Logging is silenced during the hot path** to avoid I/O stalls on very large models.

## ⚠️ Known Limitations

BIM Diff is intentionally conservative in some areas. The remaining caveats:

- **No cross-file unit normalization.** Comparing a file authored in millimetres
  against one authored in metres will produce false positives on numeric properties.
  Both files must use the same length unit. (The geometry tolerance itself *is*
  unit-aware as of v0.1.2 — but values inside property sets are not converted.)
- **`--filter-storey` is post-hoc.** The diff is computed over the full model
  and filtered afterwards. `--filter-type` is pushed into the engine selector
  for free.

## 🖥️ CLI Reference

| Flag                 | Default     | Description                                                  |
|----------------------|-------------|--------------------------------------------------------------|
| `old_file`           | required    | Path to the original IFC file.                               |
| `new_file`           | required    | Path to the revised IFC file.                                |
| `--format`           | `text`      | Output format: `text`, `json`, `csv`, `html`.                |
| `--output`, `-o`     | stdout      | Destination file (prints to stdout if omitted).              |
| `--filter-type`      | all types   | Comma-separated list of IFC types, e.g. `IfcWall,IfcDoor`.   |
| `--filter-storey`    | all storeys | Keep only elements contained in the given storey name.       |
| `--summary-only`     | `false`     | Print just the aggregated summary, no element details.       |
| `--hide-noise`       | `false`     | Strip ArchiCAD-style export noise (renovation phase, un-named quantities, Plan↔Body geometry flips). |
| `--version`          |             | Print the installed `bimdiff` version and exit.              |
| `--help`             |             | Show the CLI help.                                           |

## 🎯 Severity Scoring

Severity is computed from the percentage of non-unchanged elements, so a tweak to a 10k-element model rates "low" while a large rewrite rates "high".

| Level    | Threshold                 |
|----------|---------------------------|
| LOW      | less than 5% changed      |
| MEDIUM   | 5% to 20% changed         |
| HIGH     | more than 20% changed     |

## 🧹 Noise Filter (opt-in)

Some IFC pipelines re-stamp housekeeping properties on every export. ArchiCAD,
in particular, will mark `AC_Pset_RenovationAndPhasing.Renovation Status` on
every element on every save and recompute auto-derived `IfcElementQuantity`
values, drowning the actual semantic diff in noise. BIM Diff offers an
opt-in filter that strips these patterns:

- `geometry.presence` — IfcRepresentation Plan vs Body export flips
  (visually identical in any 3D viewer)
- `properties.AC_Pset_RenovationAndPhasing.*` — ArchiCAD phase stamp
- `properties.None.*` — un-named auto-derived quantities (NetVolume,
  NetFootprintArea, …)
- pset names containing non-printable / non-ASCII bytes (corrupted UTF-8
  from exporters that emit project-internal label names)

Modified elements whose changes are *all* noise are demoted to unchanged.
The diff engine itself stays neutral — filtering is purely opt-in
post-processing.

```python
from bimdiff import diff_ifc, filter_noise, is_noisy_change

result = diff_ifc("v1.ifc", "v2.ifc")
clean = filter_noise(result)
# Or check individual fields with is_noisy_change("properties.None.NetVolume")
```

```bash
bimdiff v1.ifc v2.ifc --hide-noise
```

On the typical ArchiCAD round-trip this drops 30–60% of the modified count
by removing pure export noise.

## ⚡ Performance

BIM Diff is built to handle real-world building models, not toy samples. The engine:

- Builds both element indexes in a single pass.
- Caches property sets, relationships, type assignments, and classification lookups per element ID.
- Hashes bounding boxes in a batch, then runs shape summarization on the two files in parallel (2-worker `ThreadPoolExecutor`).
- Uses direct dict comparison instead of reflection-based deep diffs.
- Disables logging inside the hot loop to keep I/O quiet.

In practice this keeps full diffs of mid-size models (a few thousand elements, tens of MB) well under a few seconds on a laptop. Very large models (hundreds of MB, tens of thousands of elements) still run in a single process, and you can drive a progress bar via `on_progress` if you wrap them in a UI.

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
pytest --cov=bimdiff       # with coverage
```

The test suite covers the CLI, the diff engine, the exporters, and a set of synthetic fixtures under `tests/fixtures/` (generated by `tests/fixtures/generate_fixtures.py`). You can regenerate them any time if you want to add new edge cases.

## 🤝 Contributing

Contributions are welcome. Before opening a pull request, please read [CONTRIBUTING.md](CONTRIBUTING.md).

A quick heads-up: because BIM Diff is dual-licensed (AGPL-3.0 open source plus a commercial option), **every external contributor must sign a Contributor License Agreement** before a PR can be merged. The CLA lets the project distribute your contribution under both licenses. It's a one-click flow the first time you submit a PR.

## 📄 License

BIM Diff is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0-only). See [LICENSE](LICENSE) for the full text.

If you want to integrate BIM Diff into a proprietary product, a closed-source SaaS, or any service where you cannot comply with the AGPL, a **commercial license** is available. See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

Copyright © 2026 BIM Diff contributors.

## 🙏 Acknowledgments

BIM Diff stands on the shoulders of [IfcOpenShell](https://ifcopenshell.org/), the open-source toolkit that makes working with IFC on Python actually pleasant.
