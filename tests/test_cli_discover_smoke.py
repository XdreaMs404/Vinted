from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from vinted_radar.cli import app
from vinted_radar.services.discovery import DiscoveryRunReport


class _FakeRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeDiscoveryService:
    def __init__(self) -> None:
        self.repository = _FakeRepository()
        self.calls: list[tuple[Path, object]] = []

    def run(self, options) -> DiscoveryRunReport:
        self.calls.append((Path("unused"), options))
        return DiscoveryRunReport(
            run_id="run-smoke",
            total_seed_catalogs=6,
            total_leaf_catalogs=2,
            scanned_leaf_catalogs=2,
            successful_scans=2,
            failed_scans=0,
            raw_listing_hits=3,
            unique_listing_hits=3,
        )


def test_discover_cli_reports_summary_without_touching_live_http(monkeypatch, tmp_path: Path) -> None:
    fake_service = _FakeDiscoveryService()

    def _fake_factory(*, db_path: str, timeout_seconds: float, request_delay: float, proxies=None, max_retries=3):
        assert db_path == str(tmp_path / "smoke.db")
        assert timeout_seconds == 5.0
        assert request_delay == 0.0
        return fake_service

    monkeypatch.setattr("vinted_radar.cli.build_default_service", _fake_factory)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "discover",
            "--db",
            str(tmp_path / "smoke.db"),
            "--page-limit",
            "1",
            "--max-leaf-categories",
            "2",
            "--root-scope",
            "both",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
        ],
    )

    assert result.exit_code == 0
    assert "Run: run-smoke" in result.stdout
    assert "Seeds synced: 6 catalogs (2 leaf catalogs)" in result.stdout
    assert "Listings discovered: 3 sightings, 3 unique IDs" in result.stdout
    assert fake_service.repository.closed is True
