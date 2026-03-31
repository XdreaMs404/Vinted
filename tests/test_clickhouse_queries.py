from __future__ import annotations

from pathlib import Path

from tests.clickhouse_product_test_support import make_clickhouse_product_client
from vinted_radar.query.overview_clickhouse import ClickHouseProductQueryAdapter
from vinted_radar.scoring import load_listing_score_detail


class RepositoryStub:
    def __init__(self) -> None:
        self.db_path = Path("data/stub.db")

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
            "updated_at": "2026-03-19T11:55:00+00:00",
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



def test_clickhouse_product_query_adapter_builds_overview_and_explorer_contracts() -> None:
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=make_clickhouse_product_client(),
        database="vinted_radar",
    )

    overview = adapter.overview_snapshot(now="2026-03-19T12:00:00+00:00", comparison_limit=5)
    explorer = adapter.explorer_snapshot(
        root="Femmes",
        query="robe",
        page=1,
        page_size=2,
        now="2026-03-19T12:00:00+00:00",
    )

    assert overview["summary"]["inventory"]["tracked_listings"] == 4
    assert overview["summary"]["inventory"]["sold_like_count"] == 1
    assert overview["summary"]["honesty"]["inferred_state_count"] == 1
    assert overview["comparisons"]["brand"]["status"] == "thin-support"
    assert overview["summary"]["freshness"]["acquisition_status"] == "degraded"

    assert explorer["summary"]["inventory"]["matched_listings"] == 4
    assert explorer["page"]["page"] == 1
    assert explorer["page"]["page_size"] == 2
    assert [item["listing_id"] for item in explorer["page"]["items"]] == [9003, 9001]
    assert explorer["comparisons"]["brand"]["status"] == "thin-support"



def test_clickhouse_product_query_adapter_supports_detail_score_and_history_contracts() -> None:
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=make_clickhouse_product_client(),
        database="vinted_radar",
    )

    detail = load_listing_score_detail(adapter, listing_id=9002, now="2026-03-19T12:00:00+00:00")
    history = adapter.listing_history(9002, now="2026-03-19T12:00:00+00:00", limit=12)

    assert detail is not None
    assert detail["listing_id"] == 9002
    assert detail["state_code"] == "sold_probable"
    assert detail["basis_kind"] == "inferred"
    assert detail["latest_probe"]["probe_outcome"] == "unknown"
    assert detail["state_explanation"]["follow_up_miss_count"] == 2

    assert history is not None
    assert history["summary"]["listing_id"] == 9002
    assert history["summary"]["freshness_bucket"] == "first-pass-only"
    assert history["timeline"][0]["run_id"] == "run-1"
    assert history["timeline"][0]["catalog_path"] == "Femmes > Robes"



def test_clickhouse_product_query_adapter_caches_state_inputs_for_same_now_key() -> None:
    client = make_clickhouse_product_client()
    adapter = ClickHouseProductQueryAdapter(
        repository=RepositoryStub(),
        clickhouse_client=client,
        database="vinted_radar",
    )

    adapter.overview_snapshot(now="2026-03-19T12:00:00+00:00")
    adapter.listing_explorer_page(now="2026-03-19T12:00:00+00:00", page=1, page_size=4)

    state_queries = [sql for sql in client.queries if "clickhouse-query: state-inputs" in sql]
    assert len(state_queries) == 1
