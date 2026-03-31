from __future__ import annotations

from datetime import datetime
from typing import Any

from vinted_radar.state_machine import STATE_ORDER

DEFAULT_EXPLORER_SORT = "last_seen_desc"

_PRICE_BAND_LABELS = {
    "under_20_eur": "< 20 €",
    "20_to_39_eur": "20–39 €",
    "40_plus_eur": "40 € et plus",
    "unknown": "Prix indisponible",
}
_STATE_LABELS = {
    "active": "Actif",
    "sold_observed": "Vendu observé",
    "sold_probable": "Vendu probable",
    "unavailable_non_conclusive": "Indisponible",
    "deleted": "Supprimée",
    "unknown": "Inconnu",
}


def build_explorer_filter_options(items: list[dict[str, Any]]) -> dict[str, list[dict[str, object]] | int]:
    tracked_listings = len(items)
    roots = _counted_options(
        items,
        value_getter=lambda item: item.get("root_title"),
        label_getter=lambda item: str(item.get("root_title") or "Inconnue"),
        order_key=lambda row: str(row["label"]),
    )
    catalogs = _counted_options(
        items,
        value_getter=lambda item: item.get("primary_catalog_id"),
        label_getter=lambda item: str(item.get("primary_catalog_path") or item.get("root_title") or "Catalogue inconnu"),
        include_when=lambda item: item.get("primary_catalog_id") is not None,
        order_key=lambda row: str(row["label"]),
        extra_fields=lambda item: {"catalog_id": int(item["primary_catalog_id"])},
    )
    brands = _counted_options(
        items,
        value_getter=lambda item: item.get("brand") or "unknown-brand",
        label_getter=lambda item: item.get("brand") or "Marque inconnue",
        order_key=lambda row: (-int(row["count"]), str(row["label"])),
        limit=80,
    )
    conditions = _counted_options(
        items,
        value_getter=lambda item: item.get("condition_label") or "unknown-condition",
        label_getter=lambda item: item.get("condition_label") or "État inconnu",
        order_key=lambda row: (-int(row["count"]), str(row["label"])),
        limit=40,
    )
    price_bands = _counted_options(
        items,
        value_getter=lambda item: item.get("price_band_code") or "unknown",
        label_getter=lambda item: item.get("price_band_label") or _PRICE_BAND_LABELS["unknown"],
        order_key=lambda row: (int(row.get("sort_rank") or 99), -int(row["count"]), str(row["label"])),
        extra_fields=lambda item: {"sort_rank": int(item.get("price_band_sort_order") or 99)},
    )
    states = _counted_options(
        items,
        value_getter=lambda item: item.get("state_code") or "unknown",
        label_getter=lambda item: item.get("state_label") or _STATE_LABELS["unknown"],
        order_key=lambda row: (int(row.get("sort_rank") or 99), -int(row["count"]), str(row["label"])),
        extra_fields=lambda item: {"sort_rank": int(item.get("state_sort_order") or 99)},
    )
    return {
        "tracked_listings": tracked_listings,
        "roots": [{"value": "all", "label": "All roots"}] + roots,
        "catalogs": [{"value": "", "label": "All catalogs"}] + catalogs,
        "brands": [{"value": "all", "label": "All brands"}] + brands,
        "conditions": [{"value": "all", "label": "All conditions"}] + conditions,
        "price_bands": [{"value": "all", "label": "All price bands"}] + price_bands,
        "states": [{"value": "all", "label": "All radar states"}] + states,
        "sorts": [
            {"value": "last_seen_desc", "label": "Recently seen"},
            {"value": "price_desc", "label": "Price ↓"},
            {"value": "price_asc", "label": "Price ↑"},
            {"value": "favourite_desc", "label": "Visible likes ↓"},
            {"value": "view_desc", "label": "Visible views ↓"},
            {"value": "created_at_desc", "label": "Estimated publication ↓"},
            {"value": "first_seen_desc", "label": "Radar first seen ↓"},
        ],
    }


def filter_explorer_items(
    items: list[dict[str, Any]],
    *,
    root: str | None = None,
    catalog_id: int | None = None,
    brand: str | None = None,
    condition: str | None = None,
    state: str | None = None,
    price_band: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    cleaned_query = _clean_query_text(query)
    filtered: list[dict[str, Any]] = []
    for item in items:
        if root and item.get("root_title") != root:
            continue
        if catalog_id is not None and item.get("primary_catalog_id") != int(catalog_id):
            continue
        if brand and (item.get("brand") or "unknown-brand") != brand:
            continue
        if condition and (item.get("condition_label") or "unknown-condition") != condition:
            continue
        if state and item.get("state_code") != state:
            continue
        if price_band and item.get("price_band_code") != price_band:
            continue
        if cleaned_query and not _matches_query(item, cleaned_query):
            continue
        filtered.append(item)
    return filtered


def build_explorer_summary(
    items: list[dict[str, Any]],
    *,
    support_threshold: int,
) -> dict[str, object]:
    bounded_support_threshold = max(int(support_threshold), 1)
    priced_items = [int(item["price_amount_cents"]) for item in items if item.get("price_amount_cents") is not None]
    return {
        "inventory": {
            "matched_listings": len(items),
            "sold_like_count": sum(1 for item in items if bool(item.get("sold_like"))),
            "comparison_support_threshold": bounded_support_threshold,
            "average_price_amount_cents": None
            if not priced_items
            else round(sum(priced_items) / len(priced_items), 2),
            "state_counts": {
                state_code: sum(1 for item in items if item.get("state_code") == state_code)
                for state_code in STATE_ORDER
            },
        },
        "honesty": {
            "observed_state_count": sum(1 for item in items if item.get("basis_kind") == "observed"),
            "inferred_state_count": sum(1 for item in items if item.get("basis_kind") == "inferred"),
            "unknown_state_count": sum(1 for item in items if item.get("basis_kind") == "unknown"),
            "partial_signal_count": sum(int(item.get("partial_signal") or 0) for item in items),
            "thin_signal_count": sum(int(item.get("thin_signal") or 0) for item in items),
            "estimated_publication_count": sum(int(item.get("has_estimated_publication") or 0) for item in items),
            "missing_estimated_publication_count": sum(1 for item in items if not bool(item.get("has_estimated_publication"))),
        },
    }


def build_explorer_comparison_modules(
    items: list[dict[str, Any]],
    *,
    comparison_limit: int,
    support_threshold: int,
) -> dict[str, dict[str, object]]:
    bounded_limit = max(int(comparison_limit), 1)
    bounded_support_threshold = max(int(support_threshold), 1)
    return {
        "category": build_comparison_module(
            items,
            lens="category",
            title="Catégories",
            limit=bounded_limit,
            support_threshold=bounded_support_threshold,
        ),
        "brand": build_comparison_module(
            items,
            lens="brand",
            title="Marques",
            limit=bounded_limit,
            support_threshold=bounded_support_threshold,
        ),
        "price_band": build_comparison_module(
            items,
            lens="price_band",
            title="Tranches de prix",
            limit=bounded_limit,
            support_threshold=bounded_support_threshold,
        ),
        "condition": build_comparison_module(
            items,
            lens="condition",
            title="États",
            limit=bounded_limit,
            support_threshold=bounded_support_threshold,
        ),
        "sold_state": build_comparison_module(
            items,
            lens="sold_state",
            title="Statut radar",
            limit=bounded_limit,
            support_threshold=bounded_support_threshold,
        ),
    }


def build_listing_explorer_page(
    items: list[dict[str, Any]],
    *,
    sort: str,
    page: int,
    page_size: int,
) -> dict[str, object]:
    bounded_page = max(int(page), 1)
    bounded_page_size = max(1, min(int(page_size), 100))
    normalized_sort = sort if sort in {
        "last_seen_desc",
        "price_desc",
        "price_asc",
        "favourite_desc",
        "view_desc",
        "created_at_desc",
        "first_seen_desc",
    } else DEFAULT_EXPLORER_SORT
    ordered = sorted(items, key=lambda item: _sort_key(item, normalized_sort))
    offset = (bounded_page - 1) * bounded_page_size
    page_items = ordered[offset : offset + bounded_page_size]
    total_listings = len(ordered)
    total_pages = 0 if total_listings == 0 else ((total_listings - 1) // bounded_page_size) + 1
    return {
        "page": bounded_page,
        "page_size": bounded_page_size,
        "total_listings": total_listings,
        "total_pages": total_pages,
        "has_previous_page": bounded_page > 1,
        "has_next_page": offset + len(page_items) < total_listings,
        "sort": normalized_sort,
        "items": [dict(item) for item in page_items],
    }


def build_comparison_module(
    items: list[dict[str, Any]],
    *,
    lens: str,
    title: str,
    limit: int,
    support_threshold: int,
) -> dict[str, object]:
    bounded_limit = max(int(limit), 1)
    bounded_support_threshold = max(int(support_threshold), 1)
    grouped: dict[tuple[object, str], dict[str, Any]] = {}
    for item in items:
        group = _group_for_lens(item, lens=lens)
        key = (group["value"], group["label"])
        bucket = grouped.setdefault(
            key,
            {
                "label": group["label"],
                "value": group["value"],
                "catalog_id": group.get("catalog_id"),
                "root_title": group.get("root_title"),
                "sort_rank": group.get("sort_rank"),
                "items": [],
            },
        )
        bucket["items"].append(item)

    rows: list[dict[str, object]] = []
    total_count = len(items)
    for bucket in grouped.values():
        group_items: list[dict[str, Any]] = bucket["items"]
        support_count = len(group_items)
        priced_items = [int(item["price_amount_cents"]) for item in group_items if item.get("price_amount_cents") is not None]
        rows.append(
            {
                "label": bucket["label"],
                "value": bucket["value"],
                "drilldown": {
                    "lens": lens,
                    "value": bucket["value"],
                    "filters": _drilldown_filters(
                        lens=lens,
                        value=bucket["value"],
                        catalog_id=bucket.get("catalog_id"),
                        root_title=bucket.get("root_title"),
                    ),
                },
                "inventory": {
                    "support_count": support_count,
                    "support_share": 0.0 if total_count == 0 else round(support_count / total_count, 3),
                    "average_price_amount_cents": None if not priced_items else round(sum(priced_items) / len(priced_items), 2),
                    "sold_like_count": sum(1 for item in group_items if bool(item.get("sold_like"))),
                    "sold_like_rate": 0.0 if support_count == 0 else round(sum(1 for item in group_items if bool(item.get("sold_like"))) / support_count, 3),
                    "state_counts": {
                        state_code: sum(1 for item in group_items if item.get("state_code") == state_code)
                        for state_code in STATE_ORDER
                    },
                },
                "honesty": {
                    "low_support": support_count < bounded_support_threshold,
                    "support_threshold": bounded_support_threshold,
                    "observed_state_count": sum(1 for item in group_items if item.get("basis_kind") == "observed"),
                    "inferred_state_count": sum(1 for item in group_items if item.get("basis_kind") == "inferred"),
                    "unknown_state_count": sum(1 for item in group_items if item.get("basis_kind") == "unknown"),
                    "partial_signal_count": sum(int(item.get("partial_signal") or 0) for item in group_items),
                    "thin_signal_count": sum(int(item.get("thin_signal") or 0) for item in group_items),
                    "estimated_publication_count": sum(int(item.get("has_estimated_publication") or 0) for item in group_items),
                    "missing_estimated_publication_count": sum(1 for item in group_items if not bool(item.get("has_estimated_publication"))),
                },
                "_sort_rank": bucket.get("sort_rank"),
            }
        )

    ordered_rows = sorted(rows, key=lambda row: _comparison_sort_key(row, lens=lens))[:bounded_limit]
    for row in ordered_rows:
        row.pop("_sort_rank", None)

    supported_rows = sum(1 for row in ordered_rows if not bool(row["honesty"]["low_support"]))
    if not ordered_rows:
        status = "empty"
        reason = "No tracked listings are available for this comparison lens yet."
    elif supported_rows == 0:
        status = "thin-support"
        reason = f"No lens value reaches the minimum support threshold of {bounded_support_threshold} tracked listings."
    else:
        status = "ok"
        reason = None
    return {
        "lens": lens,
        "title": title,
        "support_threshold": bounded_support_threshold,
        "status": status,
        "reason": reason,
        "total_rows": len(ordered_rows),
        "supported_rows": supported_rows,
        "thin_support_rows": len(ordered_rows) - supported_rows,
        "rows": ordered_rows,
    }


def _counted_options(
    items: list[dict[str, Any]],
    *,
    value_getter,
    label_getter,
    order_key,
    include_when=None,
    extra_fields=None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    for item in items:
        if include_when is not None and not include_when(item):
            continue
        value = value_getter(item)
        if value is None:
            continue
        key = str(value)
        bucket = buckets.setdefault(
            key,
            {
                "value": key,
                "label": f"{label_getter(item)} (0)",
                "count": 0,
                **({} if extra_fields is None else extra_fields(item)),
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["label"] = f"{label_getter(item)} ({bucket['count']})"
    ordered = sorted(buckets.values(), key=order_key)
    if limit is not None:
        ordered = ordered[: int(limit)]
    return ordered


def _group_for_lens(item: dict[str, Any], *, lens: str) -> dict[str, Any]:
    if lens == "category":
        catalog_id = item.get("primary_catalog_id")
        return {
            "value": str(catalog_id) if catalog_id is not None else str(item.get("root_title") or "unknown-root"),
            "label": str(item.get("primary_catalog_path") or item.get("root_title") or "Catégorie inconnue"),
            "catalog_id": catalog_id,
            "root_title": item.get("root_title"),
            "sort_rank": None,
        }
    if lens == "brand":
        return {
            "value": str(item.get("brand") or "unknown-brand"),
            "label": str(item.get("brand") or "Marque inconnue"),
            "sort_rank": None,
        }
    if lens == "price_band":
        value = str(item.get("price_band_code") or "unknown")
        return {
            "value": value,
            "label": str(item.get("price_band_label") or _PRICE_BAND_LABELS.get(value, value)),
            "sort_rank": int(item.get("price_band_sort_order") or 99),
        }
    if lens == "condition":
        return {
            "value": str(item.get("condition_label") or "unknown-condition"),
            "label": str(item.get("condition_label") or "État inconnu"),
            "sort_rank": None,
        }
    value = str(item.get("state_code") or "unknown")
    return {
        "value": value,
        "label": str(item.get("state_label") or _STATE_LABELS.get(value, value)),
        "sort_rank": int(item.get("state_sort_order") or 99),
    }


def _drilldown_filters(*, lens: str, value: object, catalog_id: object, root_title: object) -> dict[str, object]:
    if lens == "category" and catalog_id is not None:
        return {"catalog_id": int(catalog_id)}
    if lens == "sold_state":
        return {"state": str(value)}
    if lens == "brand":
        return {"brand": str(value)}
    if lens == "condition":
        return {"condition": str(value)}
    if lens == "price_band":
        return {"price_band": str(value)}
    if root_title is not None:
        return {"root": str(root_title)}
    return {lens: str(value)}


def _comparison_sort_key(row: dict[str, Any], *, lens: str) -> tuple[object, ...]:
    support_count = -int(row["inventory"]["support_count"])
    label = str(row["label"])
    if lens in {"price_band", "sold_state"}:
        return (support_count, int(row.get("_sort_rank") or 99), label)
    return (support_count, label)


def _matches_query(item: dict[str, Any], query: str) -> bool:
    haystacks = (
        str(item.get("listing_id") or "").lower(),
        str(item.get("title") or "").lower(),
        str(item.get("brand") or "").lower(),
        str(item.get("primary_catalog_path") or "").lower(),
        str(item.get("user_login") or "").lower(),
    )
    return any(query in haystack for haystack in haystacks)


def _clean_query_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _sort_key(item: dict[str, Any], sort: str) -> tuple[object, ...]:
    listing_id = -int(item["listing_id"])
    last_seen = -_timestamp_or_zero(item.get("last_seen_at"))
    first_seen = -_timestamp_or_zero(item.get("first_seen_at"))
    if sort == "price_desc":
        return (
            item.get("price_amount_cents") is None,
            -int(item.get("price_amount_cents") or 0),
            last_seen,
            listing_id,
        )
    if sort == "price_asc":
        return (
            item.get("price_amount_cents") is None,
            int(item.get("price_amount_cents") or 0),
            last_seen,
            listing_id,
        )
    if sort == "favourite_desc":
        return (
            item.get("favourite_count") is None,
            -int(item.get("favourite_count") or 0),
            last_seen,
            listing_id,
        )
    if sort == "view_desc":
        return (
            item.get("view_count") is None,
            -int(item.get("view_count") or 0),
            last_seen,
            listing_id,
        )
    if sort == "created_at_desc":
        return (
            item.get("created_at_ts") is None,
            -int(item.get("created_at_ts") or 0),
            last_seen,
            listing_id,
        )
    if sort == "first_seen_desc":
        return (first_seen, listing_id)
    return (last_seen, listing_id)


def _timestamp_or_zero(value: object) -> int:
    if not value:
        return 0
    try:
        return int(datetime.fromisoformat(str(value)).timestamp())
    except ValueError:
        return 0


__all__ = [
    "DEFAULT_EXPLORER_SORT",
    "build_comparison_module",
    "build_explorer_comparison_modules",
    "build_explorer_filter_options",
    "build_explorer_summary",
    "build_listing_explorer_page",
    "filter_explorer_items",
]
