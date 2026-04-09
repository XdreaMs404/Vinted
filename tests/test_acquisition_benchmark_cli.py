from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tests.test_acquisition_benchmark import _seed_repository_benchmark_db
from vinted_radar.cli import app
from vinted_radar.services.acquisition_benchmark import (
    build_acquisition_benchmark_report,
    collect_acquisition_benchmark_facts,
)


_WINDOW_START = "2026-03-25T09:00:00+00:00"
_WINDOW_END = "2026-03-25T10:00:00+00:00"


def test_acquisition_benchmark_cli_builds_redacted_artifacts_and_explains_winner(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    _seed_repository_benchmark_db(db_path)

    baseline_spec = {
        "experiment_id": "baseline-a",
        "profile": "baseline-a",
        "label": "Baseline A",
        "db_path": "benchmark.db",
        "window_started_at": _WINDOW_START,
        "window_finished_at": _WINDOW_END,
        "config": {
            "proxy": "http://bench-user:bench-pass@proxy.example:8080",
            "api_token": "super-secret-token",
            "postgres_dsn": "postgresql://bench:secret@db.example:5432/vinted_radar",
        },
        "storage_snapshots": [
            {
                "captured_at": _WINDOW_START,
                "listing_count": 100,
                "db_size_bytes": 50_000,
                "artifact_size_bytes": 5_000,
            },
            {
                "captured_at": _WINDOW_END,
                "listing_count": 108,
                "db_size_bytes": 51_600,
                "artifact_size_bytes": 5_400,
            },
        ],
        "resource_snapshots": [
            {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 35.0, "rss_mb": 256.0},
            {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 45.0, "rss_mb": 288.0},
        ],
    }
    candidate_spec = {
        "experiment_id": "candidate-b",
        "profile": "candidate-b",
        "label": "Candidate B",
        "db_path": "benchmark.db",
        "window_started_at": _WINDOW_START,
        "window_finished_at": _WINDOW_END,
        "config": {
            "proxy": "http://candidate-user:candidate-pass@proxy-b.example:9090",
            "api_token": "candidate-secret-token",
        },
        "storage_snapshots": [
            {
                "captured_at": _WINDOW_START,
                "listing_count": 100,
                "db_size_bytes": 50_000,
                "artifact_size_bytes": 5_000,
            },
            {
                "captured_at": _WINDOW_END,
                "listing_count": 112,
                "db_size_bytes": 51_800,
                "artifact_size_bytes": 5_600,
            },
        ],
        "resource_snapshots": [
            {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 30.0, "rss_mb": 240.0},
            {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 34.0, "rss_mb": 252.0},
        ],
    }

    baseline_spec_path = tmp_path / "baseline-spec.json"
    candidate_spec_path = tmp_path / "candidate-spec.json"
    baseline_spec_path.write_text(json.dumps(baseline_spec, indent=2), encoding="utf-8")
    candidate_spec_path.write_text(json.dumps(candidate_spec, indent=2), encoding="utf-8")

    json_out = tmp_path / "artifacts" / "acquisition-benchmark.json"
    markdown_out = tmp_path / "artifacts" / "acquisition-benchmark.md"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "acquisition-benchmark",
            "--spec-file",
            str(baseline_spec_path),
            "--spec-file",
            str(candidate_spec_path),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Winner: candidate-b" in result.stdout
    assert "Runner-up: baseline-a" in result.stdout
    assert "Why it won: Won on net new listings/hour: 12.00 vs 8.00." in result.stdout
    assert f"JSON artifact: {json_out}" in result.stdout
    assert f"Markdown artifact: {markdown_out}" in result.stdout

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")

    assert payload["summary"]["winner_profile"] == "candidate-b"
    baseline_declared = next(
        item["config"]["declared"]
        for item in payload["experiments"]
        if item["profile"] == "baseline-a"
    )
    candidate_declared = next(
        item["config"]["declared"]
        for item in payload["experiments"]
        if item["profile"] == "candidate-b"
    )
    assert baseline_declared["proxy"] == "http://***@proxy.example:8080"
    assert baseline_declared["api_token"] == "<redacted>"
    assert baseline_declared["postgres_dsn"] == "postgresql://***@db.example:5432/vinted_radar"
    assert candidate_declared["proxy"] == "http://***@proxy-b.example:9090"
    assert candidate_declared["api_token"] == "<redacted>"

    assert "## Method" in markdown
    assert "## Why the winner ranked first" in markdown
    assert "candidate-b 🏆" in markdown
    assert "Declared config:" in markdown
    assert "candidate-secret-token" not in markdown
    assert "candidate-pass" not in markdown



def test_acquisition_benchmark_report_cli_renders_from_raw_experiment_bundle(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    _seed_repository_benchmark_db(db_path)

    experiments = [
        collect_acquisition_benchmark_facts(
            db_path,
            experiment_id="baseline-a",
            profile="baseline-a",
            label="Baseline A",
            window_started_at=_WINDOW_START,
            window_finished_at=_WINDOW_END,
            config={
                "proxy": "http://bench-user:bench-pass@proxy.example:8080",
                "api_token": "super-secret-token",
            },
            storage_snapshots=[
                {
                    "captured_at": _WINDOW_START,
                    "listing_count": 100,
                    "db_size_bytes": 50_000,
                    "artifact_size_bytes": 5_000,
                },
                {
                    "captured_at": _WINDOW_END,
                    "listing_count": 108,
                    "db_size_bytes": 51_600,
                    "artifact_size_bytes": 5_400,
                },
            ],
            resource_snapshots=[
                {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 35.0, "rss_mb": 256.0},
                {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 45.0, "rss_mb": 288.0},
            ],
        ),
        collect_acquisition_benchmark_facts(
            db_path,
            experiment_id="candidate-b",
            profile="candidate-b",
            label="Candidate B",
            window_started_at=_WINDOW_START,
            window_finished_at=_WINDOW_END,
            config={
                "proxy": "http://candidate-user:candidate-pass@proxy-b.example:9090",
                "api_token": "candidate-secret-token",
            },
            storage_snapshots=[
                {
                    "captured_at": _WINDOW_START,
                    "listing_count": 100,
                    "db_size_bytes": 50_000,
                    "artifact_size_bytes": 5_000,
                },
                {
                    "captured_at": _WINDOW_END,
                    "listing_count": 112,
                    "db_size_bytes": 51_800,
                    "artifact_size_bytes": 5_600,
                },
            ],
            resource_snapshots=[
                {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 30.0, "rss_mb": 240.0},
                {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 34.0, "rss_mb": 252.0},
            ],
        ),
    ]

    input_path = tmp_path / "experiments.json"
    input_path.write_text(json.dumps(experiments, indent=2), encoding="utf-8")
    json_out = tmp_path / "rendered" / "report.json"
    markdown_out = tmp_path / "rendered" / "report.md"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "acquisition-benchmark-report",
            "--input",
            str(input_path),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Compared profiles: 2" in result.stdout
    assert "Winner: candidate-b" in result.stdout
    assert f"JSON artifact: {json_out}" in result.stdout
    assert f"Markdown artifact: {markdown_out}" in result.stdout

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")

    assert payload["summary"]["profile_count"] == 2
    assert payload["summary"]["winner_reason"] == "Won on net new listings/hour: 12.00 vs 8.00."
    assert payload["experiments"][0]["config"]["declared"]["api_token"] == "<redacted>"
    assert "## Leaderboard" in markdown
    assert "candidate-pass" not in markdown


def test_acquisition_benchmark_report_cli_renders_from_runner_bundle(tmp_path: Path) -> None:
    db_path = tmp_path / "benchmark.db"
    _seed_repository_benchmark_db(db_path)

    experiments = [
        collect_acquisition_benchmark_facts(
            db_path,
            experiment_id="baseline-a",
            profile="baseline-a",
            label="Baseline A",
            window_started_at=_WINDOW_START,
            window_finished_at=_WINDOW_END,
            config={
                "proxy": "http://bench-user:bench-pass@proxy.example:8080",
                "api_token": "super-secret-token",
            },
            storage_snapshots=[
                {
                    "captured_at": _WINDOW_START,
                    "listing_count": 100,
                    "db_size_bytes": 50_000,
                    "artifact_size_bytes": 5_000,
                },
                {
                    "captured_at": _WINDOW_END,
                    "listing_count": 108,
                    "db_size_bytes": 51_600,
                    "artifact_size_bytes": 5_400,
                },
            ],
            resource_snapshots=[
                {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 35.0, "rss_mb": 256.0},
                {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 45.0, "rss_mb": 288.0},
            ],
        ),
        collect_acquisition_benchmark_facts(
            db_path,
            experiment_id="candidate-b",
            profile="candidate-b",
            label="Candidate B",
            window_started_at=_WINDOW_START,
            window_finished_at=_WINDOW_END,
            config={
                "proxy": "http://candidate-user:candidate-pass@proxy-b.example:9090",
                "api_token": "candidate-secret-token",
            },
            storage_snapshots=[
                {
                    "captured_at": _WINDOW_START,
                    "listing_count": 100,
                    "db_size_bytes": 50_000,
                    "artifact_size_bytes": 5_000,
                },
                {
                    "captured_at": _WINDOW_END,
                    "listing_count": 112,
                    "db_size_bytes": 51_800,
                    "artifact_size_bytes": 5_600,
                },
            ],
            resource_snapshots=[
                {"captured_at": "2026-03-25T09:15:00+00:00", "cpu_percent": 30.0, "rss_mb": 240.0},
                {"captured_at": "2026-03-25T09:45:00+00:00", "cpu_percent": 34.0, "rss_mb": 252.0},
            ],
        ),
    ]

    report = build_acquisition_benchmark_report(experiments, generated_at="2026-03-25T10:30:00+00:00")
    bundle_path = tmp_path / "runner-bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "bundle_id": "runner-bundle-1",
                "generated_at": "2026-03-25T10:30:00+00:00",
                "benchmark_report": report,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "acquisition-benchmark-report",
            "--input",
            str(bundle_path),
            "--format",
            "markdown",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "## Leaderboard" in result.stdout
    assert "candidate-b 🏆" in result.stdout
    assert "candidate-pass" not in result.stdout
