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
    probe_summary: dict[str, object]


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
        probe_records: list[dict[str, object]] = []

        for target in targets:
            listing_id_value = int(target["listing_id"])
            probed_at = self.now_provider()
            try:
                page = self.http_client.get_text(str(target["canonical_url"]))
                parsed = parse_item_page_probe(
                    listing_id=listing_id_value,
                    response_status=page.status_code,
                    html=page.text,
                )
                self.repository.record_item_page_probe(
                    listing_id=listing_id_value,
                    probed_at=probed_at,
                    requested_url=str(target["canonical_url"]),
                    final_url=page.url,
                    response_status=page.status_code,
                    probe_outcome=parsed.probe_outcome,
                    detail=parsed.detail,
                    error_message=None,
                )
                probe_records.append(
                    {
                        "listing_id": listing_id_value,
                        "probed_at": probed_at,
                        "probe_outcome": parsed.probe_outcome,
                        "response_status": page.status_code,
                        "reason": parsed.detail.get("reason"),
                        "error_message": None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                detail = {"reason": "probe_exception", "exception_type": type(exc).__name__}
                error_message = f"{type(exc).__name__}: {exc}"
                self.repository.record_item_page_probe(
                    listing_id=listing_id_value,
                    probed_at=probed_at,
                    requested_url=str(target["canonical_url"]),
                    final_url=None,
                    response_status=None,
                    probe_outcome="unknown",
                    detail=detail,
                    error_message=error_message,
                )
                probe_records.append(
                    {
                        "listing_id": listing_id_value,
                        "probed_at": probed_at,
                        "probe_outcome": "unknown",
                        "response_status": None,
                        "reason": "probe_exception",
                        "error_message": error_message,
                    }
                )
            probed_listing_ids.append(listing_id_value)

        refreshed_inputs = self.repository.listing_state_inputs(now=reference_now, listing_id=listing_id)
        evaluations = [evaluate_listing_state(input_row, now=reference_now) for input_row in refreshed_inputs]
        summary = summarize_state_evaluations(evaluations, generated_at=reference_now)
        probe_summary = _build_probe_summary(
            probe_records,
            requested_limit=limit,
            selected_target_count=len(targets),
        )
        return StateRefreshReport(
            probed_count=len(probed_listing_ids),
            state_summary=summary,
            probed_listing_ids=probed_listing_ids,
            probe_summary=probe_summary,
        )


def build_default_state_refresh_service(
    *,
    db_path: str,
    timeout_seconds: float,
    request_delay: float,
    proxies: list[str] | None = None,
) -> StateRefreshService:
    repository = RadarRepository(db_path)
    http_client = VintedHttpClient(timeout_seconds=timeout_seconds, request_delay=request_delay, proxies=proxies)
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


def _build_probe_summary(
    records: list[dict[str, object]],
    *,
    requested_limit: int,
    selected_target_count: int,
) -> dict[str, object]:
    outcome_counts = {
        "active": 0,
        "sold": 0,
        "unavailable": 0,
        "deleted": 0,
        "unknown": 0,
    }
    reason_counts: dict[str, int] = {}
    degraded_listing_ids: list[int] = []
    direct_signal_count = 0
    inconclusive_probe_count = 0
    degraded_probe_count = 0
    anti_bot_challenge_count = 0
    http_error_count = 0
    transport_error_count = 0

    for record in records:
        probe_outcome = str(record.get("probe_outcome") or "unknown")
        reason = str(record.get("reason") or "unknown")
        listing_id = int(record.get("listing_id") or 0)
        response_status = record.get("response_status")
        degraded = _is_degraded_probe_record(reason=reason, response_status=response_status, error_message=record.get("error_message"))

        outcome_counts[probe_outcome] = outcome_counts.get(probe_outcome, 0) + 1
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        if probe_outcome in {"active", "sold", "unavailable", "deleted"}:
            direct_signal_count += 1
        if degraded:
            degraded_probe_count += 1
            degraded_listing_ids.append(listing_id)
            if reason == "anti_bot_challenge":
                anti_bot_challenge_count += 1
            elif reason == "probe_exception":
                transport_error_count += 1
            else:
                http_error_count += 1
        elif probe_outcome == "unknown":
            inconclusive_probe_count += 1

    if degraded_probe_count:
        status = "degraded"
    elif inconclusive_probe_count:
        status = "partial"
    else:
        status = "healthy"

    return {
        "status": status,
        "requested_limit": int(requested_limit),
        "selected_target_count": int(selected_target_count),
        "probed_count": len(records),
        "direct_signal_count": direct_signal_count,
        "inconclusive_probe_count": inconclusive_probe_count,
        "degraded_probe_count": degraded_probe_count,
        "anti_bot_challenge_count": anti_bot_challenge_count,
        "http_error_count": http_error_count,
        "transport_error_count": transport_error_count,
        "outcome_counts": outcome_counts,
        "reason_counts": dict(sorted(reason_counts.items())),
        "degraded_listing_ids": degraded_listing_ids,
    }


def _is_degraded_probe_record(*, reason: str, response_status: object, error_message: object) -> bool:
    if reason in {"anti_bot_challenge", "probe_exception"}:
        return True
    if error_message not in {None, ""}:
        return True
    if reason.startswith("unexpected_http_") or reason.startswith("http_"):
        return True
    if response_status in {403, 429}:
        return True
    if isinstance(response_status, int) and response_status >= 500:
        return True
    return False


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
