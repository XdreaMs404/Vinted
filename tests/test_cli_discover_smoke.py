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


def test_discover_cli_exposes_bounded_price_options_in_help() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["discover", "--help"])

    assert result.exit_code == 0
    assert "--min-price" in result.stdout
    assert "Defaults to 30.0" in result.stdout
    assert "--max-price" in result.stdout


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
    assert len(fake_service.calls) == 1
    options = fake_service.calls[0][1]
    assert options.min_price == 30.0
    assert options.max_price == 0.0


def test_discover_cli_allows_explicit_unbounded_override(monkeypatch, tmp_path: Path) -> None:
    fake_service = _FakeDiscoveryService()

    def _fake_factory(*, db_path: str, timeout_seconds: float, request_delay: float, proxies=None, max_retries=3):
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
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
            "--min-price",
            "0",
            "--max-price",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert len(fake_service.calls) == 1
    options = fake_service.calls[0][1]
    assert options.min_price == 0.0
    assert options.max_price == 0.0



def test_discover_cli_loads_webshare_proxy_file_and_auto_scales_concurrency(monkeypatch, tmp_path: Path) -> None:
    fake_service = _FakeDiscoveryService()
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text(
        "\n".join(
            [
                "45.39.4.37:5462:alice:secret",
                "216.173.80.190:6447:bob:token",
            ]
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _fake_factory(*, db_path: str, timeout_seconds: float, request_delay: float, proxies=None, max_retries=3):
        captured["proxies"] = proxies
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
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
            "--proxy-file",
            str(proxy_file),
        ],
    )

    assert result.exit_code == 0
    assert captured["proxies"] == [
        "http://alice:secret@45.39.4.37:5462",
        "http://bob:token@216.173.80.190:6447",
    ]
    assert len(fake_service.calls) == 1
    options = fake_service.calls[0][1]
    assert options.concurrency == 2
    assert "Transport: proxy-pool (2 routes, concurrency 2)" in result.stdout



def test_discover_cli_auto_concurrency_caps_at_24(monkeypatch, tmp_path: Path) -> None:
    fake_service = _FakeDiscoveryService()
    proxy_file = tmp_path / "proxies-many.txt"
    proxy_file.write_text(
        "\n".join(
            f"10.0.0.{index}:80{index:02d}:user:secret"
            for index in range(1, 31)
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("vinted_radar.cli.build_default_service", lambda **kwargs: fake_service)
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
            "1",
            "--request-delay",
            "0.0",
            "--timeout-seconds",
            "5.0",
            "--proxy-file",
            str(proxy_file),
        ],
    )

    assert result.exit_code == 0
    assert len(fake_service.calls) == 1
    options = fake_service.calls[0][1]
    assert options.concurrency == 24
    assert "Transport: proxy-pool (30 routes, concurrency 24)" in result.stdout
