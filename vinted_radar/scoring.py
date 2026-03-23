from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Iterable

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


@dataclass(frozen=True, slots=True)
class ContextSpec:
    name: str
    min_support: int
    fields: tuple[str, ...]


_CONTEXT_SPECS: tuple[ContextSpec, ...] = (
    ContextSpec("catalog_brand_condition", 4, ("primary_catalog_id", "brand", "condition_label")),
    ContextSpec("catalog_condition", 5, ("primary_catalog_id", "condition_label")),
    ContextSpec("catalog_brand", 5, ("primary_catalog_id", "brand")),
    ContextSpec("catalog", 8, ("primary_catalog_id",)),
    ContextSpec("root_condition", 10, ("root_title", "condition_label")),
    ContextSpec("root", 20, ("root_title",)),
)


@dataclass(frozen=True, slots=True)
class ListingScoreBundle:
    demand_score: float
    premium_score: float
    explanation: dict[str, object]


@dataclass(frozen=True, slots=True)
class ContextSelection:
    name: str
    sample_size: int
    prices: tuple[int, ...]


def load_listing_scores(repository: RadarRepository, *, now: str | None = None) -> list[dict[str, object]]:
    inputs = repository.listing_state_inputs(now=now)
    evaluations = [evaluate_listing_state(item, now=now) for item in inputs]
    return build_listing_scores(evaluations)



def load_listing_score_detail(
    repository: RadarRepository,
    *,
    listing_id: int,
    now: str | None = None,
) -> dict[str, object] | None:
    inputs = repository.listing_state_inputs(now=now, listing_id=listing_id)
    if not inputs:
        return None
    evaluation = evaluate_listing_state(inputs[0], now=now)
    context = _load_repository_context(repository, evaluation)
    return _enrich_listing_score(evaluation, context)



def build_listing_scores(evaluations: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    items = [dict(item) for item in evaluations]
    context_indexes = _build_context_indexes(items)
    return [_enrich_listing_score(item, _select_context(item, context_indexes)) for item in items]



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



def _enrich_listing_score(item: dict[str, object], context: ContextSelection | None) -> dict[str, object]:
    bundle = _score_listing(item, context)
    enriched = dict(item)
    enriched.update(
        {
            "demand_score": bundle.demand_score,
            "premium_score": bundle.premium_score,
            "score_explanation": bundle.explanation,
        }
    )
    return enriched



def _score_listing(item: dict[str, object], context: ContextSelection | None) -> ListingScoreBundle:
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

    expensive_signal = 0.0
    price_band_label = "unavailable"
    percentile = None
    if context is not None and item.get("price_amount_cents") is not None:
        percentile = _percentile_rank(int(item["price_amount_cents"]), list(context.prices))
        expensive_signal = round(max(0.0, (percentile - 0.5) / 0.5) * 100.0, 2)
        price_band_label = _price_band_label(percentile)
        premium_score = round((demand_score * 0.78) + (expensive_signal * 0.22), 2)
    else:
        premium_score = round(demand_score * 0.85, 2)

    explanation = {
        "factors": factor_breakdown,
        "context": None
        if context is None
        else {
            "label": context.name,
            "sample_size": context.sample_size,
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
    indexes: dict[str, dict[tuple[object, ...], list[dict[str, object]]]] = {spec.name: defaultdict(list) for spec in _CONTEXT_SPECS}
    for item in items:
        if item.get("price_amount_cents") is None:
            continue
        for spec in _CONTEXT_SPECS:
            key = _context_key(item, spec.fields)
            if key is not None:
                indexes[spec.name][key].append(item)
    return indexes



def _select_context(
    item: dict[str, object],
    context_indexes: dict[str, dict[tuple[object, ...], list[dict[str, object]]]],
) -> ContextSelection | None:
    if item.get("price_amount_cents") is None:
        return None
    for spec in _CONTEXT_SPECS:
        key = _context_key(item, spec.fields)
        if key is None:
            continue
        peers = context_indexes[spec.name].get(key, [])
        if len(peers) >= spec.min_support:
            return ContextSelection(
                name=spec.name,
                sample_size=len(peers),
                prices=tuple(int(peer["price_amount_cents"]) for peer in peers if peer.get("price_amount_cents") is not None),
            )
    return None



def _load_repository_context(repository: RadarRepository, item: dict[str, object]) -> ContextSelection | None:
    if item.get("price_amount_cents") is None:
        return None
    for spec in _CONTEXT_SPECS:
        filters = _context_filters(item, spec.fields)
        if not filters:
            continue
        peer_prices = repository.listing_price_context_peer_prices(**_context_filter_kwargs(filters))
        if len(peer_prices) >= spec.min_support:
            return ContextSelection(name=spec.name, sample_size=len(peer_prices), prices=tuple(peer_prices))
    return None



def _context_filters(item: dict[str, object], fields: tuple[str, ...]) -> tuple[tuple[str, object], ...]:
    filters: list[tuple[str, object]] = []
    for field in fields:
        value = _context_field_value(field, item.get(field))
        if value is not None and value != "":
            filters.append((field, value))
    return tuple(filters)



def _context_key(item: dict[str, object], fields: tuple[str, ...]) -> tuple[object, ...] | None:
    filters = _context_filters(item, fields)
    if not filters:
        return None
    return tuple(value for _, value in filters)



def _context_filter_kwargs(filters: tuple[tuple[str, object], ...]) -> dict[str, object | None]:
    kwargs: dict[str, object | None] = {
        "primary_catalog_id": None,
        "root_title": None,
        "brand": None,
        "condition_label": None,
    }
    for field, value in filters:
        kwargs[field] = value
    return kwargs



def _context_field_value(field: str, value: object) -> object | None:
    if field in {"root_title", "brand", "condition_label"}:
        return _norm(value)
    return value



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
