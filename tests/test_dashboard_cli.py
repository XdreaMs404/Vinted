from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vinted_radar.cli import app


def test_dashboard_cli_reports_local_urls_and_calls_server(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_serve_dashboard(
        *,
        db_path: Path,
        host: str,
        port: int,
        now: str | None,
        base_path: str | None = None,
        public_base_url: str | None = None,
    ) -> None:
        captured.update(
            {
                "db_path": db_path,
                "host": host,
                "port": port,
                "now": now,
                "base_path": base_path,
                "public_base_url": public_base_url,
            }
        )

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
    assert "Overview home: http://127.0.0.1:8765/" in result.stdout
    assert "Dashboard API: http://127.0.0.1:8765/api/dashboard" in result.stdout
    assert "Explorer: http://127.0.0.1:8765/explorer" in result.stdout
    assert "Runtime: http://127.0.0.1:8765/runtime" in result.stdout
    assert "Runtime API: http://127.0.0.1:8765/api/runtime" in result.stdout
    assert "Listing detail: http://127.0.0.1:8765/listings/<id>" in result.stdout
    assert "Listing detail API: http://127.0.0.1:8765/api/listings/<id>" in result.stdout
    assert "Health: http://127.0.0.1:8765/health" in result.stdout
    assert captured == {
        "db_path": Path(tmp_path / "dash.db"),
        "host": "127.0.0.1",
        "port": 8765,
        "now": "2026-03-19T12:00:00+00:00",
        "base_path": "",
        "public_base_url": None,
    }



def test_dashboard_cli_reports_proxy_aware_urls(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _fake_serve_dashboard(**kwargs) -> None:
        captured.update(kwargs)

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
            "8782",
            "--base-path",
            "/radar",
            "--public-base-url",
            "https://radar.example.com/radar",
        ],
    )

    assert result.exit_code == 0
    assert "Dashboard URL: https://radar.example.com/radar" in result.stdout
    assert "Overview home: https://radar.example.com/radar/" in result.stdout
    assert "Explorer: https://radar.example.com/radar/explorer" in result.stdout
    assert "Runtime: https://radar.example.com/radar/runtime" in result.stdout
    assert "Listing detail: https://radar.example.com/radar/listings/<id>" in result.stdout
    assert captured["base_path"] == "/radar"
    assert captured["public_base_url"] == "https://radar.example.com/radar"
