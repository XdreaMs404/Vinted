from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Callable, Iterable

from vinted_radar.repository import RadarRepository
from vinted_radar.state_machine import evaluate_listing_state, summarize_state_evaluations

DEMAND_STATE_COMPONENT = {
    "active": 18.0,
    "sold_observed": 90.0,
    "sold_probable": 74.0,
    "unavailable_non_conclusive": 42.0,
    "deleted": 24.0,
    "unknown": 10.0,
}
CONFIDENCE_COMPONENT = {"high": 12.0, "medium": 7.0, "low": 2.0}
BASIS_COMPONENT = {"observed": 8.0, "inferred": 3.0, "unknown": 0.0}
FRESHNESS_COMPONENT = {"fresh-followup": 10.0, "aging-followup": 6.0, "stale-followup": 2.0, "first-pass-only": 4.0}

_CONTEXT_BUILDERS: list[tuple[str, int, Callable[[dict[str, object]], tuple[object, ...] | None]]] = [
    ("catalog_brand_condition", 4, lambda item: _maybe_key(item.get("primary_catalog_id"), _norm(item.get("brand")), _norm(item.get("condition_label")))),
    ("catalog_condition", 5, lambda item: _maybe_key(item.get("primary_catalog_id"), _norm(item.get("condition_label")))),
    ("catalog_brand", 5, lambda item: _maybe_key(item.get("primary_catalog_id"), _norm(item.get("brand")))),
    ("catalog", 8, lambda item: _maybe_key(item.get("primary_catalog_id"))),
    ("root_condition", 10, lambda item: _maybe_key(_norm(item.get("root_title")), _norm(item.get("condition_label")))),
    ("root", 20, lambda item: _maybe_key(_norm(item.get("root_title")))),
]


@dataclass(frozen=True, slots=True)
class ListingScoreBundle:
    demand_score: float
    premium_score: float
    explanation: dict[str, object]


def load_listing_scores(repository: RadarRepository, *, now: str | None = None) -> list[dict[str, object]]:
    inputs = repository.listing_state_inputs(now=now)
    evaluations = [evaluate_listing_state(item, now=now) for item in inputs]
    return build_listing_scores(evaluations)


def build_listing_scores(evaluations: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    items = [dict(item) for item in evaluations]
    context_indexes = _build_context_indexes(items)
    scored: list[dict[str, object]] = []
    for item in items:
        bundle = _score_listing(item, context_indexes)
        enriched = dict(item)
        enriched.update(
            {
                "demand_score": bundle.demand_score,
                "premium_score": bundle.premium_score,
                "score_explanation": bundle.explanation,
            }
        )
        scored.append(enriched)
    return scored


def build_rankings(listing_scores: list[dict[str, object]], *, kind: str, limit: int = 20) -> list[dict[str, object]]:
    score_field = _score_field(kind)
    rankings = sorted(
        listing_scores,
        key=lambda item: (
            -float(item[score_field]),
            -float(item["demand_score"]),
            -float(item.get("confidence_score") or 0.0),
            int(item["listing_id"]),
        ),
    )
    return rankings[:limit]


def build_market_summary(
    listing_scores: list[dict[str, object]],
    repository: RadarRepository,
    *,
    now: str | None = None,
    limit: int = 8,
) -> dict[str, object]:
    generated_at = now or datetime.now(UTC).replace(microsecond=0).isoformat()
    overall_state = summarize_state_evaluations(listing_scores, generated_at=generated_at)
    segments: list[dict[str, object]] = []
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for item in listing_scores:
        if item.get("primary_catalog_id") is not None:
            grouped[int(item["primary_catalog_id"])] .append(item)

    for catalog_id, items in grouped.items():
        if len(items) < 3:
            continue
        path = str(items[0].get("primary_catalog_path") or items[0].get("root_title") or f"catalog:{catalog_id}")
        demand_values = [float(item["demand_score"]) for item in items]
        premium_values = [float(item["premium_score"]) for item in items]
        sold_like_count = sum(1 for item in items if item["state_code"] in {"sold_observed", "sold_probable"})
        avg_demand = round(sum(demand_values) / len(demand_values), 2)
        avg_premium = round(sum(premium_values) / len(premium_values), 2)
        avg_price_cents = round(sum(int(item["price_amount_cents"]) for item in items if item.get("price_amount_cents") is not None) / max(sum(1 for item in items if item.get("price_amount_cents") is not None), 1), 2)
        recent_arrivals = sum(1 for item in items if float(item.get("last_seen_age_hours") or 0.0) <= 24.0 and int(item.get("observation_count") or 0) == 1)
        latest_count, previous_count = _latest_segment_scan_counts(repository, catalog_id)
        visible_delta = latest_count - previous_count if latest_count is not None and previous_count is not None else 0
        sold_like_rate = sold_like_count / len(items)
        performance_score = round((avg_demand * 0.68) + (avg_premium * 0.32), 2)
        rising_score = round((avg_demand * 0.35) + (sold_like_rate * 40.0) + (recent_arrivals * 6.0) + max(visible_delta, 0) * 4.0, 2)
        segments.append(
            {
                "catalog_id": catalog_id,
                "catalog_path": path,
                "root_title": items[0].get("root_title"),
                "tracked_listings": len(items),
                "avg_demand_score": avg_demand,
                "avg_premium_score": avg_premium,
                "avg_price_amount_cents": avg_price_cents,
                "sold_like_count": sold_like_count,
                "sold_like_rate": round(sold_like_rate, 3),
                "recent_arrivals": recent_arrivals,
                "latest_scan_count": latest_count,
                "previous_scan_count": previous_count,
                "visible_delta": visible_delta,
                "performance_score": performance_score,
                "rising_score": rising_score,
                "top_state_mix": _state_mix(items),
            }
        )

    performing = sorted(segments, key=lambda item: (-float(item["performance_score"]), -int(item["tracked_listings"]), int(item["catalog_id"])))[:limit]
    rising = sorted(segments, key=lambda item: (-float(item["rising_score"]), -int(item["recent_arrivals"]), int(item["catalog_id"])))[:limit]
    return {
        "generated_at": generated_at,
        "overall": overall_state["overall"],
        "performing_segments": performing,
        "rising_segments": rising,
    }


def build_listing_score_detail(listing_scores: list[dict[str, object]], listing_id: int) -> dict[str, object] | None:
    for item in listing_scores:
        if int(item["listing_id"]) == listing_id:
            return item
    return None


def _score_listing(item: dict[str, object], context_indexes: dict[str, dict[tuple[object, ...], list[dict[str, object]]]]) -> ListingScoreBundle:
    state_code = str(item["state_code"])
    confidence_label = str(item["confidence_label"])
    basis_kind = str(item["basis_kind"])
    freshness_bucket = str(item.get("freshness_bucket") or "first-pass-only")
    observation_count = int(item.get("observation_count") or 0)
    follow_up_miss_count = int(item.get("follow_up_miss_count") or 0)

    factor_breakdown = {
        "state": DEMAND_STATE_COMPONENT[state_code],
        "confidence": CONFIDENCE_COMPONENT[confidence_label],
        "basis": BASIS_COMPONENT[basis_kind],
        "freshness": FRESHNESS_COMPONENT.get(freshness_bucket, 0.0),
        "history_depth": min(max(observation_count - 1, 0) * 4.0, 12.0),
        "follow_up_miss": min(follow_up_miss_count * 6.0, 18.0),
    }
    demand_score = round(min(sum(factor_breakdown.values()), 100.0), 2)

    context = _select_context(item, context_indexes)
    expensive_signal = 0.0
    price_band_label = "unavailable"
    if context is not None and item.get("price_amount_cents") is not None:
        percentile = _percentile_rank(int(item["price_amount_cents"]), [int(peer["price_amount_cents"]) for peer in context["peers"] if peer.get("price_amount_cents") is not None])
        expensive_signal = round(max(0.0, (percentile - 0.5) / 0.5) * 100.0, 2)
        price_band_label = _price_band_label(percentile)
        premium_score = round((demand_score * 0.78) + (expensive_signal * 0.22), 2)
    else:
        percentile = None
        premium_score = round(demand_score * 0.85, 2)

    explanation = {
        "factors": factor_breakdown,
        "context": None
        if context is None
        else {
            "label": context["name"],
            "sample_size": context["sample_size"],
            "price_percentile": percentile,
            "price_band_label": price_band_label,
            "expensive_signal": expensive_signal,
        },
        "notes": [
            "Demand score is anchored in current state, confidence, freshness, history depth, and follow-up misses.",
            "Premium score keeps demand primary and only adds a contextual price boost when peer support is strong enough.",
        ],
    }
    return ListingScoreBundle(demand_score=demand_score, premium_score=premium_score, explanation=explanation)


def _build_context_indexes(items: list[dict[str, object]]) -> dict[str, dict[tuple[object, ...], list[dict[str, object]]]]:
    indexes: dict[str, dict[tuple[object, ...], list[dict[str, object]]]] = {name: defaultdict(list) for name, _, _ in _CONTEXT_BUILDERS}
    for item in items:
        if item.get("price_amount_cents") is None:
            continue
        for name, _, builder in _CONTEXT_BUILDERS:
            key = builder(item)
            if key is not None:
                indexes[name][key].append(item)
    return indexes


def _select_context(item: dict[str, object], context_indexes: dict[str, dict[tuple[object, ...], list[dict[str, object]]]]) -> dict[str, object] | None:
    if item.get("price_amount_cents") is None:
        return None
    for name, min_support, builder in _CONTEXT_BUILDERS:
        key = builder(item)
        if key is None:
            continue
        peers = context_indexes[name].get(key, [])
        if len(peers) >= min_support:
            return {"name": name, "sample_size": len(peers), "peers": peers}
    return None


def _maybe_key(*parts: object) -> tuple[object, ...] | None:
    cleaned = [part for part in parts if part is not None and part != ""]
    if not cleaned:
        return None
    return tuple(cleaned)


def _norm(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower() or None


def _percentile_rank(value: int, peers: list[int]) -> float:
    if not peers:
        return 0.5
    sorted_peers = sorted(peers)
    below = sum(1 for peer in sorted_peers if peer < value)
    equal = sum(1 for peer in sorted_peers if peer == value)
    return round((below + (equal / 2.0)) / len(sorted_peers), 3)


def _price_band_label(percentile: float) -> str:
    if percentile >= 0.67:
        return "premium"
    if percentile >= 0.33:
        return "mid"
    return "budget"


def _score_field(kind: str) -> str:
    return "demand_score" if kind == "demand" else "premium_score"


def _latest_segment_scan_counts(repository: RadarRepository, catalog_id: int) -> tuple[int | None, int | None]:
    rows = repository.connection.execute(
        """
        SELECT listing_count
        FROM catalog_scans
        WHERE catalog_id = ? AND success = 1
        ORDER BY fetched_at DESC, run_id DESC
        LIMIT 2
        """,
        (catalog_id,),
    ).fetchall()
    if not rows:
        return None, None
    latest = int(rows[0]["listing_count"])
    previous = int(rows[1]["listing_count"]) if len(rows) > 1 else None
    return latest, previous


def _state_mix(items: list[dict[str, object]]) -> dict[str, int]:
    mix = defaultdict(int)
    for item in items:
        mix[str(item["state_code"])] += 1
    return dict(mix)
