from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path

from typer.testing import CliRunner

from tests.clickhouse_product_test_support import make_clickhouse_product_client
from vinted_radar.cli import app
from vinted_radar.query.overview_clickhouse import ClickHouseProductQueryAdapter


class RepositoryStub:
    def __init__(self) -> None:
        self.db_path = Path("data/stub.db")

    @property
    def connection(self):
        return None

    def coverage_summary(self, run_id: str | None = None):
        return {
            "run": {
                "run_id": "run-3",
                "started_at": "2026-03-19T10:00:00+00:00",
                "finished_at": "2026-03-19T10:10:00+00:00",
            },
            "failures": [],
        }

    def runtime_status(self, *, limit: int = 10, now: str | None = None):
        return {
            "status": "scheduled",
            "phase": "waiting",
            "updated_at": now or "2026-03-19T12:00:00+00:00",
            "next_resume_at": "2026-03-19T12:05:00+00:00",
            "paused_at": None,
            "controller": {"heartbeat": {"is_stale": False}},
            "latest_cycle": {"status": "completed", "started_at": "2026-03-19T11:00:00+00:00"},
            "acquisition": {
                "status": "degraded",
                "reasons": ["1 state-refresh probe hit anti-bot or challenge-shaped pages."],
                "latest_state_refresh_summary": {"degraded_probe_count": 1, "inconclusive_probe_count": 0},
                "probe_issue_examples": [{"listing_id": 9002, "reason": "anti_bot_challenge"}],
            },
        }



def test_clickhouse_feature_marts_export_surfaces_rollups_change_facts_and_traceability() -> None:
    client = make_clickhouse_product_client()
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=client,
        database="vinted_radar",
    )

    export = adapter.feature_marts_export(
        listing_ids=[9001, 9002],
        start_date="2026-03-17",
        end_date="2026-03-19",
        segment_lens="all",
        now="2026-03-19T12:00:00+00:00",
        limit=10,
    )

    assert export["source"] == "clickhouse.feature_marts"
    assert export["listing_day"]["row_count"] == 3
    assert export["segment_day"]["row_count"] == 2
    assert export["price_change"]["row_count"] == 1
    assert export["state_transition"]["row_count"] == 1
    assert export["evidence_packs"]["row_count"] == 2

    listing_day_row = export["listing_day"]["rows"][0]
    assert listing_day_row["trace"]["manifest_ids"]
    assert listing_day_row["trace"]["run_ids"]

    price_change_row = export["price_change"]["rows"][0]
    assert price_change_row["price_delta_amount_cents"] == 100
    assert price_change_row["trace"]["run_id"] == "run-3"
    assert price_change_row["trace"]["catalog_scan_terminal"] is True

    state_transition_row = export["state_transition"]["rows"][0]
    assert state_transition_row["transition_label"] == "active → sold_probable"
    assert state_transition_row["trace"]["missing_from_scan"] is True

    evidence_pack = next(row for row in export["evidence_packs"]["rows"] if row["listing_id"] == 9002)
    assert evidence_pack["current"]["state_code"] == "sold_probable"
    assert evidence_pack["window"]["state_transition_count"] == 1
    assert "manifest-transition-run-3" in evidence_pack["trace"]["manifest_ids"]
    assert any("evidence-inspect --manifest-id manifest-transition-run-3" in command for command in evidence_pack["trace"]["inspect_examples"])

    feature_queries = [sql for sql in client.queries if "clickhouse-query: feature-mart" in sql]
    assert len(feature_queries) >= 4



def test_clickhouse_feature_marts_filter_segment_lens_and_listing_ids() -> None:
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=make_clickhouse_product_client(),
        database="vinted_radar",
    )

    brand_rows = adapter.segment_day_mart(segment_lens="brand", start_date="2026-03-19", end_date="2026-03-19", limit=5)
    listing_rows = adapter.listing_day_mart(listing_ids=[9001], start_date="2026-03-18", end_date="2026-03-19", limit=5)

    assert len(brand_rows) == 1
    assert brand_rows[0]["segment_lens"] == "brand"
    assert brand_rows[0]["segment_label"] == "Zara"
    assert [row["listing_id"] for row in listing_rows] == [9001, 9001]



def test_feature_marts_cli_emits_json_export(monkeypatch, tmp_path: Path) -> None:
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=make_clickhouse_product_client(),
        database="vinted_radar",
    )

    @contextmanager
    def _open_backend(_db: Path):
        yield adapter

    monkeypatch.setattr("vinted_radar.cli._open_product_query_backend", _open_backend)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "feature-marts",
            "--db",
            str(tmp_path / "source.db"),
            "--listing-id",
            "9001",
            "--listing-id",
            "9002",
            "--start-date",
            "2026-03-17",
            "--end-date",
            "2026-03-19",
            "--segment-lens",
            "brand",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["filters"]["listing_ids"] == [9001, 9002]
    assert payload["filters"]["segment_lens"] == "brand"
    assert payload["segment_day"]["row_count"] == 1
    assert payload["evidence_packs"]["row_count"] == 2
