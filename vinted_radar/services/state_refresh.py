from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from vinted_radar.http import VintedHttpClient
from vinted_radar.parsers.item_page import parse_item_page_probe
from vinted_radar.repository import RadarRepository
from vinted_radar.state_machine import evaluate_listing_state, summarize_state_evaluations


@dataclass(frozen=True, slots=True)
class StateRefreshReport:
    probed_count: int
    state_summary: dict[str, object]
    probed_listing_ids: list[int]


class StateRefreshService:
    def __init__(
        self,
        repository: RadarRepository,
        http_client: VintedHttpClient,
        *,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.http_client = http_client
        self.now_provider = now_provider or _utc_now

    def refresh(self, *, limit: int = 10, listing_id: int | None = None, now: str | None = None) -> StateRefreshReport:
        reference_now = now or self.now_provider()
        inputs = self.repository.listing_state_inputs(now=reference_now, listing_id=listing_id)
        targets = _select_probe_targets(inputs, limit=limit, listing_id=listing_id)
        probed_listing_ids: list[int] = []

        for target in targets:
            probed_at = self.now_provider()
            try:
                page = self.http_client.get_text(str(target["canonical_url"]))
                parsed = parse_item_page_probe(
                    listing_id=int(target["listing_id"]),
                    response_status=page.status_code,
                    html=page.text,
                )
                self.repository.record_item_page_probe(
                    listing_id=int(target["listing_id"]),
                    probed_at=probed_at,
                    requested_url=str(target["canonical_url"]),
                    final_url=page.url,
                    response_status=page.status_code,
                    probe_outcome=parsed.probe_outcome,
                    detail=parsed.detail,
                    error_message=None,
                )
            except Exception as exc:  # noqa: BLE001
                self.repository.record_item_page_probe(
                    listing_id=int(target["listing_id"]),
                    probed_at=probed_at,
                    requested_url=str(target["canonical_url"]),
                    final_url=None,
                    response_status=None,
                    probe_outcome="unknown",
                    detail={"reason": "probe_exception", "exception_type": type(exc).__name__},
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            probed_listing_ids.append(int(target["listing_id"]))

        refreshed_inputs = self.repository.listing_state_inputs(now=reference_now, listing_id=listing_id)
        evaluations = [evaluate_listing_state(input_row, now=reference_now) for input_row in refreshed_inputs]
        summary = summarize_state_evaluations(evaluations, generated_at=reference_now)
        return StateRefreshReport(probed_count=len(probed_listing_ids), state_summary=summary, probed_listing_ids=probed_listing_ids)


def build_default_state_refresh_service(*, db_path: str, timeout_seconds: float, request_delay: float) -> StateRefreshService:
    repository = RadarRepository(db_path)
    http_client = VintedHttpClient(timeout_seconds=timeout_seconds, request_delay=request_delay)
    return StateRefreshService(repository=repository, http_client=http_client)


def _select_probe_targets(inputs: list[dict[str, object]], *, limit: int, listing_id: int | None) -> list[dict[str, object]]:
    if listing_id is not None:
        return inputs[:1]

    candidates = [
        item
        for item in inputs
        if _needs_probe(item)
    ]
    candidates.sort(
        key=lambda item: (
            -(int(item.get("follow_up_miss_count") or 0)),
            -(1 if int(item.get("observation_count") or 0) == 1 else 0),
            -float(item.get("last_seen_age_hours") or 0.0),
            -int(item.get("signal_completeness") or 0),
            int(item["listing_id"]),
        )
    )
    return candidates[:limit]


def _needs_probe(item: dict[str, object]) -> bool:
    latest_probe = item.get("latest_probe")
    latest_probe_at = latest_probe.get("probed_at") if isinstance(latest_probe, dict) else None
    probe_stale = latest_probe_at is None or str(latest_probe_at) < str(item.get("last_seen_at"))
    follow_up_miss_count = int(item.get("follow_up_miss_count") or 0)
    observation_count = int(item.get("observation_count") or 0)
    return probe_stale and (follow_up_miss_count > 0 or observation_count == 1)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
