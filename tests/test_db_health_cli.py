from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.repository import RadarRepository


def test_db_health_reports_healthy_database(tmp_path: Path) -> None:
    db_path = tmp_path / "healthy.db"
    with RadarRepository(db_path):
        pass

    runner = CliRunner()
    result = runner.invoke(app, ["db-health", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Database:" in result.stdout
    assert "quick_check: ok" in result.stdout
    assert "Healthy: yes" in result.stdout


def test_db_health_reports_non_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.db"
    db_path.write_text("not a sqlite database", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["db-health", "--db", str(db_path)])

    assert result.exit_code == 1
    assert "Schema error:" in result.stdout
    assert "Healthy: no" in result.stdout


def test_coverage_points_to_db_health_when_database_is_invalid(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.db"
    db_path.write_text("not a sqlite database", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["coverage", "--db", str(db_path)])

    assert result.exit_code == 1
    assert "Coverage query failed:" in result.stdout
    assert "Inspect DB health with:" in result.stdout
