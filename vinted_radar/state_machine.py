from __future__ import annotations

from datetime import UTC, datetime

HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.55

STATE_ORDER = [
    "active",
    "sold_observed",
    "sold_probable",
    "unavailable_non_conclusive",
    "deleted",
    "unknown",
]


def evaluate_listing_state(evidence: dict[str, object], *, now: str | None = None) -> dict[str, object]:
    now_dt = _coerce_now(now)
    result = dict(evidence)
    reasons: list[str] = []
    latest_probe = evidence.get("latest_probe")
    probe_outcome = latest_probe.get("probe_outcome") if isinstance(latest_probe, dict) else None

    if probe_outcome == "deleted":
        reasons.append(f"Item page returned a distinct deletion signal ({latest_probe.get('response_status')}).")
        return _finalize(result, now_dt, state_code="deleted", basis_kind="observed", confidence_score=0.97, reasons=reasons)
    if probe_outcome == "sold":
        reasons.append("Item page buy signal is closed, so the listing appears sold on the public page.")
        return _finalize(result, now_dt, state_code="sold_observed", basis_kind="observed", confidence_score=0.91, reasons=reasons)
    if probe_outcome == "active":
        reasons.append("Item page is still publicly buyable, which is direct active evidence.")
        return _finalize(result, now_dt, state_code="active", basis_kind="observed", confidence_score=0.95, reasons=reasons)
    if probe_outcome == "unavailable":
        reasons.append("Item page is reachable but publicly unavailable without a distinct sold/deleted signal.")
        return _finalize(result, now_dt, state_code="unavailable_non_conclusive", basis_kind="observed", confidence_score=0.62, reasons=reasons)
    if probe_outcome == "unknown":
        reasons.append("The latest item-page probe was inconclusive, so history remains the safer signal.")

    if bool(evidence.get("seen_in_latest_primary_scan")):
        reasons.append("The listing was observed in the latest successful scan of its primary catalog.")
        return _finalize(result, now_dt, state_code="active", basis_kind="observed", confidence_score=0.9, reasons=reasons)

    follow_up_miss_count = int(evidence.get("follow_up_miss_count") or 0)
    observation_count = int(evidence.get("observation_count") or 0)
    last_seen_age_hours = float(evidence.get("last_seen_age_hours") or 0.0)

    if follow_up_miss_count >= 2:
        reasons.append(f"The primary catalog was rescanned {follow_up_miss_count} times after the last sighting without seeing the listing again.")
        if observation_count >= 2:
            reasons.append("The listing was seen repeatedly before disappearing, which strengthens the sell-through signal.")
        confidence = 0.72 if follow_up_miss_count == 2 else 0.82
        return _finalize(result, now_dt, state_code="sold_probable", basis_kind="inferred", confidence_score=confidence, reasons=reasons)

    if follow_up_miss_count == 1:
        reasons.append("The listing missed one follow-up scan after its last sighting, but that is not distinct enough to call sold or deleted.")
        return _finalize(result, now_dt, state_code="unavailable_non_conclusive", basis_kind="inferred", confidence_score=0.46, reasons=reasons)

    latest_primary_scan_run_id = evidence.get("latest_primary_scan_run_id")
    if latest_primary_scan_run_id is None and last_seen_age_hours <= 24.0:
        reasons.append("The listing was seen recently, but there is no newer successful primary-catalog scan yet.")
        return _finalize(result, now_dt, state_code="active", basis_kind="inferred", confidence_score=0.58, reasons=reasons)

    if last_seen_age_hours > 72.0:
        reasons.append("The last sighting is too old and there is no distinct contrary evidence, so the current state stays unknown.")
        return _finalize(result, now_dt, state_code="unknown", basis_kind="unknown", confidence_score=0.24, reasons=reasons)

    reasons.append("There is not enough direct or repeated absence evidence to classify the current state confidently.")
    return _finalize(result, now_dt, state_code="unknown", basis_kind="unknown", confidence_score=0.32, reasons=reasons)


def summarize_state_evaluations(evaluations: list[dict[str, object]], *, generated_at: str | None = None) -> dict[str, object]:
    summary = {
        "generated_at": generated_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "overall": {
            "tracked_listings": len(evaluations),
            **{state: 0 for state in STATE_ORDER},
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "observed_basis": 0,
            "inferred_basis": 0,
            "unknown_basis": 0,
        },
        "by_root": [],
    }
    by_root: dict[str, dict[str, object]] = {}

    for evaluation in evaluations:
        state_code = str(evaluation["state_code"])
        confidence_label = str(evaluation["confidence_label"])
        basis_kind = str(evaluation["basis_kind"])
        root_title = str(evaluation.get("root_title") or "Unknown")

        summary["overall"][state_code] += 1
        summary["overall"][f"{confidence_label}_confidence"] += 1
        summary["overall"][f"{basis_kind}_basis"] += 1

        if root_title not in by_root:
            by_root[root_title] = {
                "root_title": root_title,
                "tracked_listings": 0,
                **{state: 0 for state in STATE_ORDER},
            }
        by_root[root_title]["tracked_listings"] += 1
        by_root[root_title][state_code] += 1

    summary["by_root"] = [by_root[key] for key in sorted(by_root)]
    return summary


def _finalize(
    evidence: dict[str, object],
    now_dt: datetime,
    *,
    state_code: str,
    basis_kind: str,
    confidence_score: float,
    reasons: list[str],
) -> dict[str, object]:
    result = dict(evidence)
    result.update(
        {
            "state_code": state_code,
            "basis_kind": basis_kind,
            "confidence_score": round(confidence_score, 2),
            "confidence_label": _confidence_label(confidence_score),
            "state_explanation": {
                "reasons": reasons,
                "evaluated_at": now_dt.replace(microsecond=0).isoformat(),
                "follow_up_miss_count": int(evidence.get("follow_up_miss_count") or 0),
                "last_seen_age_hours": float(evidence.get("last_seen_age_hours") or 0.0),
                "latest_probe_outcome": (evidence.get("latest_probe") or {}).get("probe_outcome") if isinstance(evidence.get("latest_probe"), dict) else None,
            },
        }
    )
    return result


def _confidence_label(score: float) -> str:
    if score >= HIGH_CONFIDENCE:
        return "high"
    if score >= MEDIUM_CONFIDENCE:
        return "medium"
    return "low"


def _coerce_now(now: str | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return datetime.fromisoformat(now)
