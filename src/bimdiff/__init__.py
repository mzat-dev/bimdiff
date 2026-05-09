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

"""bimdiff - Semantic diff engine for IFC/BIM models.

Usage::

    from bimdiff import diff_ifc
    result = diff_ifc("old.ifc", "new.ifc")
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from bimdiff.differ import ProgressCallback, diff_ifc
from bimdiff.filters import filter_noise, is_noisy_change
from bimdiff.models import (
    CanonicalEntity,
    DiffResult,
    DiffSummary,
    ModifiedEntity,
    PropertyChange,
)
from bimdiff.reporter import export_csv, export_html, export_json

# Single source of truth: pyproject.toml. Falls back to "0+unknown" only when
# the package was imported without being installed (e.g. PYTHONPATH src/).
try:
    __version__ = _pkg_version("bimdiff")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0+unknown"

__all__ = [
    "diff_ifc",
    "export_csv",
    "export_html",
    "export_json",
    "filter_noise",
    "is_noisy_change",
    "CanonicalEntity",
    "DiffResult",
    "DiffSummary",
    "ModifiedEntity",
    "ProgressCallback",
    "PropertyChange",
]
