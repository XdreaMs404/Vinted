from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app


def test_dashboard_cli_reports_local_urls_and_calls_server(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_serve_dashboard(*, db_path: Path, host: str, port: int, now: str | None) -> None:
        captured.update({"db_path": db_path, "host": host, "port": port, "now": now})

    monkeypatch.setattr("vinted_radar.cli.serve_dashboard", _fake_serve_dashboard)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "dashboard",
            "--db",
            str(tmp_path / "dash.db"),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--now",
            "2026-03-19T12:00:00+00:00",
        ],
    )

    assert result.exit_code == 0
    assert "Dashboard URL: http://127.0.0.1:8765" in result.stdout
    assert "Dashboard API: http://127.0.0.1:8765/api/dashboard" in result.stdout
    assert "Runtime API: http://127.0.0.1:8765/api/runtime" in result.stdout
    assert captured == {
        "db_path": Path(tmp_path / "dash.db"),
        "host": "127.0.0.1",
        "port": 8765,
        "now": "2026-03-19T12:00:00+00:00",
    }
