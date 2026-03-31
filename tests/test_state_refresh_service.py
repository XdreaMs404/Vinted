from __future__ import annotations

from types import SimpleNamespace

from vinted_radar.services.state_refresh import StateRefreshService


class FakeRepository:
    def __init__(self) -> None:
        self.recorded: list[dict[str, object]] = []

    def state_refresh_probe_targets(self, *, limit: int = 10, now: str | None = None) -> list[dict[str, object]]:
        return [{"listing_id": 9001, "canonical_url": "https://www.vinted.fr/items/9001-active"}][:limit]

    def record_item_page_probe(self, **kwargs) -> str:
        self.recorded.append(dict(kwargs))
        return "probe-1"

    def listing_state_inputs(self, *, now: str | None = None, listing_id: int | None = None) -> list[dict[str, object]]:
        raise AssertionError("runtime refresh should not load full listing_state_inputs when state summary is skipped")


class FakeHttpClient:
    def get_text(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, text="<html></html>", url=url)



def test_state_refresh_service_runtime_mode_skips_global_state_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "vinted_radar.services.state_refresh.parse_item_page_probe",
        lambda listing_id, response_status, html: SimpleNamespace(probe_outcome="active", detail={"reason": "buy_signal_open"}),
    )
    repository = FakeRepository()
    service = StateRefreshService(repository=repository, http_client=FakeHttpClient(), now_provider=lambda: "2026-03-23T10:00:00+00:00")

    report = service.refresh(limit=1, include_state_summary=False)

    assert report.probed_count == 1
    assert report.probed_listing_ids == [9001]
    assert report.probe_summary["status"] == "healthy"
    assert report.state_summary["status"] == "skipped"
    assert len(repository.recorded) == 1
    assert repository.recorded[0]["listing_id"] == 9001



def test_state_refresh_service_projects_probe_rows_into_mutable_truth(monkeypatch) -> None:
    monkeypatch.setattr(
        "vinted_radar.services.state_refresh.parse_item_page_probe",
        lambda listing_id, response_status, html: SimpleNamespace(probe_outcome="active", detail={"reason": "buy_signal_open"}),
    )

    class FakeMutableTruthRepository:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def project_state_refresh_probes(self, *, probe_rows, projected_at: str, event_id: str, manifest_id=None) -> None:
            self.calls.append(
                {
                    "probe_rows": [dict(row) for row in probe_rows],
                    "projected_at": projected_at,
                    "event_id": event_id,
                    "manifest_id": manifest_id,
                }
            )

    repository = FakeRepository()
    mutable_truth_repository = FakeMutableTruthRepository()
    service = StateRefreshService(
        repository=repository,
        http_client=FakeHttpClient(),
        now_provider=lambda: "2026-03-23T10:00:00+00:00",
        mutable_truth_repository=mutable_truth_repository,
    )

    report = service.refresh(limit=1, include_state_summary=False)

    assert report.probed_count == 1
    assert len(mutable_truth_repository.calls) == 1
    assert mutable_truth_repository.calls[0]["projected_at"] == "2026-03-23T10:00:00+00:00"
    assert mutable_truth_repository.calls[0]["probe_rows"][0]["listing_id"] == 9001
    assert mutable_truth_repository.calls[0]["probe_rows"][0]["probe_outcome"] == "active"
