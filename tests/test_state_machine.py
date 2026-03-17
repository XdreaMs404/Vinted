from __future__ import annotations

from vinted_radar.state_machine import evaluate_listing_state


def _base_evidence() -> dict[str, object]:
    return {
        "listing_id": 9001,
        "title": "Example",
        "root_title": "Femmes",
        "first_seen_at": "2026-03-17T10:00:00+00:00",
        "last_seen_at": "2026-03-18T10:00:00+00:00",
        "last_seen_age_hours": 1.0,
        "observation_count": 2,
        "total_sightings": 2,
        "signal_completeness": 6,
        "follow_up_miss_count": 0,
        "latest_primary_scan_run_id": "run-2",
        "last_observed_run_id": "run-2",
        "seen_in_latest_primary_scan": True,
        "latest_probe": None,
    }


def test_active_observed_when_seen_in_latest_primary_scan() -> None:
    result = evaluate_listing_state(_base_evidence(), now="2026-03-18T11:00:00+00:00")

    assert result["state_code"] == "active"
    assert result["basis_kind"] == "observed"
    assert result["confidence_label"] == "high"


def test_sold_observed_when_probe_closes_buy_signal() -> None:
    evidence = _base_evidence()
    evidence.update({
        "seen_in_latest_primary_scan": False,
        "follow_up_miss_count": 1,
        "latest_probe": {"probe_outcome": "sold", "response_status": 200, "probed_at": "2026-03-18T11:00:00+00:00"},
    })

    result = evaluate_listing_state(evidence, now="2026-03-18T11:00:00+00:00")

    assert result["state_code"] == "sold_observed"
    assert result["basis_kind"] == "observed"


def test_sold_probable_after_repeated_follow_up_misses() -> None:
    evidence = _base_evidence()
    evidence.update({
        "seen_in_latest_primary_scan": False,
        "follow_up_miss_count": 3,
        "latest_primary_scan_run_id": "run-5",
        "last_observed_run_id": "run-2",
        "latest_probe": None,
    })

    result = evaluate_listing_state(evidence, now="2026-03-20T11:00:00+00:00")

    assert result["state_code"] == "sold_probable"
    assert result["basis_kind"] == "inferred"
    assert result["confidence_label"] in {"medium", "high"}


def test_unavailable_non_conclusive_after_single_follow_up_miss() -> None:
    evidence = _base_evidence()
    evidence.update({
        "seen_in_latest_primary_scan": False,
        "follow_up_miss_count": 1,
        "latest_primary_scan_run_id": "run-3",
        "last_observed_run_id": "run-2",
        "latest_probe": None,
    })

    result = evaluate_listing_state(evidence, now="2026-03-19T11:00:00+00:00")

    assert result["state_code"] == "unavailable_non_conclusive"
    assert result["basis_kind"] == "inferred"


def test_deleted_when_probe_returns_404_signal() -> None:
    evidence = _base_evidence()
    evidence.update({
        "seen_in_latest_primary_scan": False,
        "latest_probe": {"probe_outcome": "deleted", "response_status": 404, "probed_at": "2026-03-19T11:00:00+00:00"},
    })

    result = evaluate_listing_state(evidence, now="2026-03-19T11:00:00+00:00")

    assert result["state_code"] == "deleted"
    assert result["basis_kind"] == "observed"


def test_unknown_when_history_is_old_and_inconclusive() -> None:
    evidence = _base_evidence()
    evidence.update({
        "seen_in_latest_primary_scan": False,
        "latest_primary_scan_run_id": None,
        "follow_up_miss_count": 0,
        "last_seen_age_hours": 96.0,
        "latest_probe": {"probe_outcome": "unknown", "response_status": 500, "probed_at": "2026-03-20T11:00:00+00:00"},
    })

    result = evaluate_listing_state(evidence, now="2026-03-20T11:00:00+00:00")

    assert result["state_code"] == "unknown"
    assert result["basis_kind"] == "unknown"
