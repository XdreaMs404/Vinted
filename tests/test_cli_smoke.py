from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app


def test_coverage_command_bootstraps_database_and_reports_empty_state(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "smoke.db"

    result = runner.invoke(app, ["coverage", "--db", str(db_path)])

    assert result.exit_code == 0
    assert db_path.exists()
    assert "No discovery runs recorded yet." in result.stdout
