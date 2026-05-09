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

import json

from click.testing import CliRunner

from bimdiff.cli import main

FIXTURES = "tests/fixtures"


def test_cli_default_text_output():
    runner = CliRunner()
    result = runner.invoke(main, [f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc"])
    assert result.exit_code == 0
    assert "BIM Diff Report" in result.output
    assert "Severity:" in result.output


def test_cli_json_output():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc", "--format", "json"
    ])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "added" in parsed


def test_cli_csv_output():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc", "--format", "csv"
    ])
    assert result.exit_code == 0
    assert "status,global_id,ifc_type" in result.output


def test_cli_html_output():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc", "--format", "html"
    ])
    assert result.exit_code == 0
    assert "<html" in result.output
    assert "BIM Diff Report" in result.output


def test_cli_output_file(tmp_path):
    runner = CliRunner()
    out_file = str(tmp_path / "report.json")
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
        "--format", "json", "-o", out_file
    ])
    assert result.exit_code == 0
    assert "Report written to" in result.output
    with open(out_file) as f:
        parsed = json.loads(f.read())
    assert "added" in parsed


def test_cli_summary_only():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc", "--summary-only"
    ])
    assert result.exit_code == 0
    assert "BIM Diff Report" in result.output


def test_cli_filter_type():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
        "--format", "json", "--filter-type", "IfcWall"
    ])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    # All entities should be IfcWall
    for entity in parsed["added"]:
        assert entity["ifc_type"] == "IfcWall"
    for entity in parsed["removed"]:
        assert entity["ifc_type"] == "IfcWall"


def test_cli_filter_storey_includes_modified():
    runner = CliRunner()
    result = runner.invoke(main, [
        f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
        "--format", "json", "--filter-storey", "Level 1"
    ])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    for m in parsed.get("modified", []):
        assert m.get("storey") == "Level 1"


def test_cli_filter_type_passes_selector_to_core():
    """--filter-type X,Y must reach diff_ifc as selector='X, Y' so the engine
    narrows the index at build time instead of doing a full diff and filtering
    after the fact."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch("bimdiff.cli.diff_ifc") as mock_diff:
        # Return a minimal valid DiffResult so the rest of the CLI keeps working
        from bimdiff.models import DiffResult, DiffSummary
        mock_diff.return_value = DiffResult(
            summary=DiffSummary(
                total_added=0, total_removed=0, total_modified=0, total_unchanged=0,
                severity="low",
            )
        )
        runner.invoke(main, [
            f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
            "--filter-type", "IfcWall,IfcDoor",
        ])
    assert mock_diff.called
    _, kwargs = mock_diff.call_args
    assert kwargs.get("selector") == "IfcWall, IfcDoor"


def test_cli_hide_noise_flag_invokes_filter():
    """--hide-noise must route the result through bimdiff.filters.filter_noise."""
    from unittest.mock import patch

    from bimdiff.models import DiffResult, DiffSummary

    runner = CliRunner()
    with patch("bimdiff.filters.filter_noise") as mock_filter:
        mock_filter.return_value = DiffResult(
            summary=DiffSummary(
                total_added=0, total_removed=0, total_modified=0, total_unchanged=0,
                severity="low",
            )
        )
        result = runner.invoke(main, [
            f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
            "--hide-noise",
        ])
    assert result.exit_code == 0
    assert mock_filter.called


def test_cli_hide_noise_flag_default_off():
    """Without --hide-noise the engine result reaches the renderer untouched."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch("bimdiff.filters.filter_noise") as mock_filter:
        runner.invoke(main, [
            f"{FIXTURES}/simple_v1.ifc", f"{FIXTURES}/simple_v2.ifc",
        ])
    assert not mock_filter.called


def test_cli_missing_file():
    runner = CliRunner()
    result = runner.invoke(main, ["nonexistent.ifc", "also_missing.ifc"])
    assert result.exit_code != 0
