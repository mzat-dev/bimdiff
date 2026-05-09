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

"""Internal mixins composing :class:`bimdiff.differ.DiffEngine`.

This package is private — its API is not part of the public ``bimdiff``
contract and may change without notice.
"""

from bimdiff._engine.caches import IfcCacheMixin
from bimdiff._engine.comparators import ComparatorsMixin
from bimdiff._engine.extractor import EntityExtractorMixin
from bimdiff._engine.geometry import GeometryMixin
from bimdiff._engine.summary import SummaryMixin

__all__ = [
    "IfcCacheMixin",
    "ComparatorsMixin",
    "EntityExtractorMixin",
    "GeometryMixin",
    "SummaryMixin",
]
