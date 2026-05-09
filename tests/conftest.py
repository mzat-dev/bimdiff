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

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_v1_path() -> Path:
    return FIXTURES_DIR / "simple_v1.ifc"


@pytest.fixture
def simple_v2_path() -> Path:
    return FIXTURES_DIR / "simple_v2.ifc"


@pytest.fixture
def identical_path() -> Path:
    return FIXTURES_DIR / "identical.ifc"


@pytest.fixture
def empty_path() -> Path:
    return FIXTURES_DIR / "empty.ifc"


@pytest.fixture
def duplicate_guid_path() -> Path:
    return FIXTURES_DIR / "duplicate_guid.ifc"


@pytest.fixture
def material_v1_path() -> Path:
    return FIXTURES_DIR / "material_v1.ifc"


@pytest.fixture
def material_v2_path() -> Path:
    return FIXTURES_DIR / "material_v2.ifc"


@pytest.fixture
def added_props_v1_path() -> Path:
    return FIXTURES_DIR / "added_props_v1.ifc"


@pytest.fixture
def added_props_v2_path() -> Path:
    return FIXTURES_DIR / "added_props_v2.ifc"
