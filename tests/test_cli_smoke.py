from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import sys

from typer.testing import CliRunner

from tests.test_dashboard import _seed_dashboard_db
from vinted_radar.cli import app
from vinted_radar.dashboard import start_dashboard_server


def test_coverage_command_bootstraps_database_and_reports_empty_state(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "smoke.db"

    result = runner.invoke(app, ["coverage", "--db", str(db_path)])

    assert result.exit_code == 0
    assert db_path.exists()
    assert "No discovery runs recorded yet." in result.stdout



def test_verify_vps_serving_script_passes_against_local_prefixed_server(tmp_path: Path) -> None:
    db_path = tmp_path / "dashboard.db"
    _seed_dashboard_db(db_path)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = start_dashboard_server(
        db_path=db_path,
        host="127.0.0.1",
        port=port,
        now="2026-03-19T12:00:00+00:00",
        base_path="/radar",
        public_base_url=f"http://127.0.0.1:{port}/radar",
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/verify_vps_serving.py",
                "--base-url",
                f"http://127.0.0.1:{port}/radar",
                "--listing-id",
                "9002",
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        server.stop()

    assert result.returncode == 0, result.stderr
    assert "VPS serving verification passed:" in result.stdout
    assert f"http://127.0.0.1:{port}/radar/listings/9002" in result.stdout
