from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import json
import re
from typing import Any

from vinted_radar.query.detail_clickhouse import load_clickhouse_state_inputs
from vinted_radar.state_machine import evaluate_listing_state

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VIEW_LISTING_DAY = "mart_listing_day"
_VIEW_SEGMENT_DAY = "mart_segment_day"
_VIEW_PRICE_CHANGE = "mart_price_change"
_VIEW_STATE_TRANSITION = "mart_state_transition"
_PRICE_BAND_LABELS = {
    "under_20_eur": "< 20 €",
    "20_to_39_eur": "20–39 €",
    "40_plus_eur": "40 € et plus",
    "unknown": "Prix indisponible",
}


def fetch_clickhouse_listing_day_mart(
    clickhouse_client: object,
    *,
    database: str,
    listing_ids: Sequence[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    where_sql = _mart_where_sql(
        date_field="bucket_date",
        listing_ids=listing_ids,
        start_date=start_date,
        end_date=end_date,
    )
    sql = f"""
    /* clickhouse-query: feature-mart dataset=listing_day listing_ids={_marker_listing_ids(listing_ids)} start_date={_marker_date(start_date)} end_date={_marker_date(end_date)} segment_lens=all limit={max(int(limit), 1)} */
    SELECT *
    FROM {safe_database}.{_VIEW_LISTING_DAY}
    {where_sql}
    ORDER BY bucket_date DESC, listing_id DESC
    LIMIT {max(int(limit), 1)}
    """
    return [_hydrate_rollup_row(row) for row in _query_rows(clickhouse_client, sql)]



def fetch_clickhouse_segment_day_mart(
    clickhouse_client: object,
    *,
    database: str,
    segment_lens: str = "all",
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    normalized_lens = _normalize_segment_lens(segment_lens)
    where_clauses: list[str] = []
    if normalized_lens != "all":
        where_clauses.append(f"segment_lens = {_sql_string(normalized_lens)}")
    if start_date is not None:
        where_clauses.append(f"bucket_date >= {_sql_string(_safe_date(start_date, field_name='start_date'))}")
    if end_date is not None:
        where_clauses.append(f"bucket_date <= {_sql_string(_safe_date(end_date, field_name='end_date'))}")
    where_sql = "" if not where_clauses else "WHERE " + " AND ".join(where_clauses)
    sql = f"""
    /* clickhouse-query: feature-mart dataset=segment_day listing_ids=all start_date={_marker_date(start_date)} end_date={_marker_date(end_date)} segment_lens={normalized_lens} limit={max(int(limit), 1)} */
    SELECT *
    FROM {safe_database}.{_VIEW_SEGMENT_DAY}
    {where_sql}
    ORDER BY bucket_date DESC, segment_lens ASC, segment_label ASC
    LIMIT {max(int(limit), 1)}
    """
    return [_hydrate_rollup_row(row) for row in _query_rows(clickhouse_client, sql)]



def fetch_clickhouse_price_change_mart(
    clickhouse_client: object,
    *,
    database: str,
    listing_ids: Sequence[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    where_sql = _mart_where_sql(
        date_field="change_date",
        listing_ids=listing_ids,
        start_date=start_date,
        end_date=end_date,
    )
    sql = f"""
    /* clickhouse-query: feature-mart dataset=price_change listing_ids={_marker_listing_ids(listing_ids)} start_date={_marker_date(start_date)} end_date={_marker_date(end_date)} segment_lens=all limit={max(int(limit), 1)} */
    SELECT *
    FROM {safe_database}.{_VIEW_PRICE_CHANGE}
    {where_sql}
    ORDER BY occurred_at DESC, listing_id DESC
    LIMIT {max(int(limit), 1)}
    """
    return [_hydrate_change_row(row, dataset="price_change") for row in _query_rows(clickhouse_client, sql)]



def fetch_clickhouse_state_transition_mart(
    clickhouse_client: object,
    *,
    database: str,
    listing_ids: Sequence[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    where_sql = _mart_where_sql(
        date_field="change_date",
        listing_ids=listing_ids,
        start_date=start_date,
        end_date=end_date,
    )
    sql = f"""
    /* clickhouse-query: feature-mart dataset=state_transition listing_ids={_marker_listing_ids(listing_ids)} start_date={_marker_date(start_date)} end_date={_marker_date(end_date)} segment_lens=all limit={max(int(limit), 1)} */
    SELECT *
    FROM {safe_database}.{_VIEW_STATE_TRANSITION}
    {where_sql}
    ORDER BY occurred_at DESC, listing_id DESC
    LIMIT {max(int(limit), 1)}
    """
    return [_hydrate_change_row(row, dataset="state_transition") for row in _query_rows(clickhouse_client, sql)]



def load_clickhouse_evidence_packs(
    clickhouse_client: object,
    *,
    database: str,
    listing_ids: Sequence[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    now: str | None = None,
    limit: int = 25,
) -> list[dict[str, object]]:
    generated_at = _generated_at(now)
    normalized_listing_ids = _normalize_listing_ids(listing_ids)
    state_inputs = load_clickhouse_state_inputs(
        clickhouse_client,
        database=database,
        now=generated_at,
        listing_id=normalized_listing_ids[0] if normalized_listing_ids and len(normalized_listing_ids) == 1 else None,
    )
    if normalized_listing_ids is not None:
        allowed = set(normalized_listing_ids)
        state_inputs = [row for row in state_inputs if int(row.get("listing_id") or 0) in allowed]
    state_inputs = state_inputs[: max(int(limit), 1)]

    if not state_inputs and normalized_listing_ids is not None:
        target_listing_ids = list(normalized_listing_ids)
    else:
        target_listing_ids = [int(row["listing_id"]) for row in state_inputs]
    if not target_listing_ids:
        return []

    mart_limit = max(max(int(limit), 1) * max(len(target_listing_ids), 1) * 8, 32)
    listing_days = fetch_clickhouse_listing_day_mart(
        clickhouse_client,
        database=database,
        listing_ids=target_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=mart_limit,
    )
    price_changes = fetch_clickhouse_price_change_mart(
        clickhouse_client,
        database=database,
        listing_ids=target_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=mart_limit,
    )
    state_transitions = fetch_clickhouse_state_transition_mart(
        clickhouse_client,
        database=database,
        listing_ids=target_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=mart_limit,
    )

    listing_days_by_listing: dict[int, list[dict[str, object]]] = defaultdict(list)
    price_changes_by_listing: dict[int, list[dict[str, object]]] = defaultdict(list)
    state_transitions_by_listing: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in listing_days:
        listing_days_by_listing[int(row["listing_id"])].append(dict(row))
    for row in price_changes:
        price_changes_by_listing[int(row["listing_id"])].append(dict(row))
    for row in state_transitions:
        state_transitions_by_listing[int(row["listing_id"])].append(dict(row))

    packs: list[dict[str, object]] = []
    seen_pack_ids: set[int] = set()
    for state_input in state_inputs:
        listing_id = int(state_input["listing_id"])
        seen_pack_ids.add(listing_id)
        evaluation = evaluate_listing_state(dict(state_input), now=generated_at)
        price_band = _price_band_fields(state_input.get("price_amount_cents"))
        pack_listing_days = listing_days_by_listing.get(listing_id, [])
        pack_price_changes = price_changes_by_listing.get(listing_id, [])
        pack_state_transitions = state_transitions_by_listing.get(listing_id, [])
        trace = _combine_trace(
            listing_days=pack_listing_days,
            price_changes=pack_price_changes,
            state_transitions=pack_state_transitions,
        )
        packs.append(
            {
                "pack_id": f"listing-{listing_id}",
                "listing_id": listing_id,
                "generated_at": generated_at,
                "current": {
                    "listing_id": listing_id,
                    "title": state_input.get("title"),
                    "canonical_url": state_input.get("canonical_url"),
                    "source_url": state_input.get("source_url"),
                    "image_url": state_input.get("image_url"),
                    "brand": state_input.get("brand"),
                    "size_label": state_input.get("size_label"),
                    "condition_label": state_input.get("condition_label"),
                    "price_amount_cents": state_input.get("price_amount_cents"),
                    "total_price_amount_cents": state_input.get("total_price_amount_cents"),
                    "favourite_count": state_input.get("favourite_count"),
                    "view_count": state_input.get("view_count"),
                    "root_title": state_input.get("root_title"),
                    "primary_catalog_id": state_input.get("primary_catalog_id"),
                    "primary_root_catalog_id": state_input.get("primary_root_catalog_id"),
                    "primary_catalog_path": state_input.get("primary_catalog_path"),
                    "price_band_code": price_band["price_band_code"],
                    "price_band_label": price_band["price_band_label"],
                    "state_code": evaluation.get("state_code"),
                    "basis_kind": evaluation.get("basis_kind"),
                    "confidence_label": evaluation.get("confidence_label"),
                    "confidence_score": evaluation.get("confidence_score"),
                    "state_explanation": evaluation.get("state_explanation"),
                },
                "window": {
                    "first_seen_at": state_input.get("first_seen_at"),
                    "last_seen_at": state_input.get("last_seen_at"),
                    "last_seen_age_hours": state_input.get("last_seen_age_hours"),
                    "observation_count": state_input.get("observation_count"),
                    "total_sightings": state_input.get("total_sightings"),
                    "average_revisit_hours": state_input.get("average_revisit_hours"),
                    "follow_up_miss_count": state_input.get("follow_up_miss_count"),
                    "latest_primary_scan_run_id": state_input.get("latest_primary_scan_run_id"),
                    "latest_primary_scan_at": state_input.get("latest_primary_scan_at"),
                    "listing_day_count": len(pack_listing_days),
                    "price_change_count": len(pack_price_changes),
                    "state_transition_count": len(pack_state_transitions),
                },
                "listing_days": pack_listing_days,
                "price_changes": pack_price_changes,
                "state_transitions": pack_state_transitions,
                "trace": {
                    **trace,
                    "inspect_examples": _inspect_examples(trace),
                },
            }
        )

    for listing_id in target_listing_ids:
        if listing_id in seen_pack_ids:
            continue
        pack_listing_days = listing_days_by_listing.get(listing_id, [])
        pack_price_changes = price_changes_by_listing.get(listing_id, [])
        pack_state_transitions = state_transitions_by_listing.get(listing_id, [])
        trace = _combine_trace(
            listing_days=pack_listing_days,
            price_changes=pack_price_changes,
            state_transitions=pack_state_transitions,
        )
        packs.append(
            {
                "pack_id": f"listing-{listing_id}",
                "listing_id": listing_id,
                "generated_at": generated_at,
                "current": {
                    "listing_id": listing_id,
                    "title": None,
                    "canonical_url": None,
                    "source_url": None,
                    "image_url": None,
                    "brand": None,
                    "size_label": None,
                    "condition_label": None,
                    "price_amount_cents": None,
                    "total_price_amount_cents": None,
                    "favourite_count": None,
                    "view_count": None,
                    "root_title": None,
                    "primary_catalog_id": None,
                    "primary_root_catalog_id": None,
                    "primary_catalog_path": None,
                    "price_band_code": "unknown",
                    "price_band_label": _PRICE_BAND_LABELS["unknown"],
                    "state_code": None,
                    "basis_kind": None,
                    "confidence_label": None,
                    "confidence_score": None,
                    "state_explanation": None,
                },
                "window": {
                    "first_seen_at": None,
                    "last_seen_at": None,
                    "last_seen_age_hours": None,
                    "observation_count": 0,
                    "total_sightings": 0,
                    "average_revisit_hours": None,
                    "follow_up_miss_count": None,
                    "latest_primary_scan_run_id": None,
                    "latest_primary_scan_at": None,
                    "listing_day_count": len(pack_listing_days),
                    "price_change_count": len(pack_price_changes),
                    "state_transition_count": len(pack_state_transitions),
                },
                "listing_days": pack_listing_days,
                "price_changes": pack_price_changes,
                "state_transitions": pack_state_transitions,
                "trace": {
                    **trace,
                    "inspect_examples": _inspect_examples(trace),
                },
            }
        )

    packs.sort(
        key=lambda pack: (
            str(pack["window"].get("last_seen_at") or ""),
            int(pack["listing_id"]),
        ),
        reverse=True,
    )
    return packs[: max(int(limit), 1)]



def load_clickhouse_feature_marts_export(
    clickhouse_client: object,
    *,
    database: str,
    listing_ids: Sequence[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    segment_lens: str = "all",
    now: str | None = None,
    limit: int = 25,
) -> dict[str, object]:
    generated_at = _generated_at(now)
    normalized_listing_ids = _normalize_listing_ids(listing_ids)
    normalized_segment_lens = _normalize_segment_lens(segment_lens)
    listing_day_rows = fetch_clickhouse_listing_day_mart(
        clickhouse_client,
        database=database,
        listing_ids=normalized_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=max(int(limit), 1),
    )
    segment_day_rows = fetch_clickhouse_segment_day_mart(
        clickhouse_client,
        database=database,
        segment_lens=normalized_segment_lens,
        start_date=start_date,
        end_date=end_date,
        limit=max(int(limit), 1),
    )
    price_change_rows = fetch_clickhouse_price_change_mart(
        clickhouse_client,
        database=database,
        listing_ids=normalized_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=max(int(limit), 1),
    )
    state_transition_rows = fetch_clickhouse_state_transition_mart(
        clickhouse_client,
        database=database,
        listing_ids=normalized_listing_ids,
        start_date=start_date,
        end_date=end_date,
        limit=max(int(limit), 1),
    )
    evidence_packs = load_clickhouse_evidence_packs(
        clickhouse_client,
        database=database,
        listing_ids=normalized_listing_ids,
        start_date=start_date,
        end_date=end_date,
        now=generated_at,
        limit=max(int(limit), 1),
    )
    return {
        "generated_at": generated_at,
        "source": "clickhouse.feature_marts",
        "filters": {
            "listing_ids": [] if normalized_listing_ids is None else list(normalized_listing_ids),
            "start_date": _safe_date(start_date, field_name="start_date") if start_date is not None else None,
            "end_date": _safe_date(end_date, field_name="end_date") if end_date is not None else None,
            "segment_lens": normalized_segment_lens,
            "limit": max(int(limit), 1),
        },
        "listing_day": {"row_count": len(listing_day_rows), "rows": listing_day_rows},
        "segment_day": {"row_count": len(segment_day_rows), "rows": segment_day_rows},
        "price_change": {"row_count": len(price_change_rows), "rows": price_change_rows},
        "state_transition": {"row_count": len(state_transition_rows), "rows": state_transition_rows},
        "evidence_packs": {"row_count": len(evidence_packs), "rows": evidence_packs},
    }



def _hydrate_rollup_row(row: Mapping[str, object]) -> dict[str, object]:
    hydrated = dict(row)
    manifest_ids = _string_list(row.get("manifest_ids"))
    source_event_ids = _string_list(row.get("source_event_ids"))
    run_ids = _string_list(row.get("run_ids"))
    hydrated["price_band_label"] = hydrated.get("price_band_label") or _PRICE_BAND_LABELS.get(
        str(hydrated.get("price_band_code") or "unknown"),
        _PRICE_BAND_LABELS["unknown"],
    )
    hydrated["trace"] = {
        "manifest_ids": manifest_ids,
        "source_event_ids": source_event_ids,
        "run_ids": run_ids,
        "window_started_at": hydrated.get("window_started_at"),
        "window_ended_at": hydrated.get("window_ended_at"),
    }
    hydrated["manifest_ids"] = manifest_ids
    hydrated["source_event_ids"] = source_event_ids
    hydrated["run_ids"] = run_ids
    return hydrated



def _hydrate_change_row(row: Mapping[str, object], *, dataset: str) -> dict[str, object]:
    hydrated = dict(row)
    metadata = _load_json_object(hydrated.get("metadata_json"))
    change = _load_json_object(hydrated.get("change_json"))
    hydrated["trace"] = {
        "manifest_id": hydrated.get("manifest_id"),
        "source_event_id": hydrated.get("source_event_id"),
        "source_event_type": hydrated.get("source_event_type"),
        "run_id": metadata.get("run_id"),
        "page_number": metadata.get("page_number"),
        "card_position": metadata.get("card_position"),
        "catalog_scan_terminal": metadata.get("catalog_scan_terminal"),
        "missing_from_scan": metadata.get("missing_from_scan"),
        "capture_source": metadata.get("capture_source"),
    }
    hydrated["metadata"] = metadata
    hydrated["change"] = change
    if dataset == "price_change":
        hydrated["price_delta_amount_cents"] = _delta(
            hydrated.get("previous_price_amount_cents"),
            hydrated.get("current_price_amount_cents"),
        )
        hydrated["total_price_delta_amount_cents"] = _delta(
            hydrated.get("previous_total_price_amount_cents"),
            hydrated.get("current_total_price_amount_cents"),
        )
    else:
        previous_state = hydrated.get("previous_state_code") or "unknown"
        current_state = hydrated.get("current_state_code") or "unknown"
        hydrated["transition_label"] = f"{previous_state} → {current_state}"
    return hydrated



def _combine_trace(
    *,
    listing_days: Sequence[Mapping[str, object]],
    price_changes: Sequence[Mapping[str, object]],
    state_transitions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    manifest_ids = {
        manifest_id
        for row in listing_days
        for manifest_id in _string_list(row.get("manifest_ids"))
        if manifest_id
    }
    source_event_ids = {
        event_id
        for row in listing_days
        for event_id in _string_list(row.get("source_event_ids"))
        if event_id
    }
    run_ids = {
        run_id
        for row in listing_days
        for run_id in _string_list(row.get("run_ids"))
        if run_id
    }
    window_started_values = [row.get("window_started_at") for row in listing_days if row.get("window_started_at")]
    window_ended_values = [row.get("window_ended_at") for row in listing_days if row.get("window_ended_at")]

    for row in list(price_changes) + list(state_transitions):
        trace = dict(row.get("trace") or {})
        manifest_id = trace.get("manifest_id")
        source_event_id = trace.get("source_event_id")
        run_id = trace.get("run_id")
        if manifest_id:
            manifest_ids.add(str(manifest_id))
        if source_event_id:
            source_event_ids.add(str(source_event_id))
        if run_id:
            run_ids.add(str(run_id))
        occurred_at = row.get("occurred_at")
        if occurred_at:
            window_started_values.append(occurred_at)
            window_ended_values.append(occurred_at)

    return {
        "manifest_ids": sorted(manifest_ids),
        "source_event_ids": sorted(source_event_ids),
        "run_ids": sorted(run_ids),
        "window_started_at": min((str(value) for value in window_started_values), default=None),
        "window_ended_at": max((str(value) for value in window_ended_values), default=None),
    }



def _inspect_examples(trace: Mapping[str, object]) -> list[str]:
    examples: list[str] = []
    manifest_ids = _string_list(trace.get("manifest_ids"))
    source_event_ids = _string_list(trace.get("source_event_ids"))
    for manifest_id in manifest_ids[:3]:
        examples.append(f"python -m vinted_radar.cli evidence-inspect --manifest-id {manifest_id}")
    for source_event_id in source_event_ids[:3]:
        examples.append(f"python -m vinted_radar.cli evidence-inspect --event-id {source_event_id}")
    return examples



def _mart_where_sql(
    *,
    date_field: str,
    listing_ids: Sequence[int] | None,
    start_date: str | None,
    end_date: str | None,
) -> str:
    where_clauses: list[str] = []
    normalized_listing_ids = _normalize_listing_ids(listing_ids)
    if normalized_listing_ids is not None:
        ids_sql = ", ".join(str(value) for value in normalized_listing_ids)
        where_clauses.append(f"listing_id IN ({ids_sql})")
    if start_date is not None:
        where_clauses.append(f"{date_field} >= {_sql_string(_safe_date(start_date, field_name='start_date'))}")
    if end_date is not None:
        where_clauses.append(f"{date_field} <= {_sql_string(_safe_date(end_date, field_name='end_date'))}")
    return "" if not where_clauses else "WHERE " + " AND ".join(where_clauses)



def _normalize_segment_lens(value: str) -> str:
    normalized = str(value or "all").strip().lower()
    if normalized not in {"all", "category", "brand"}:
        raise ValueError("segment_lens must be one of: all, category, brand.")
    return normalized



def _normalize_listing_ids(listing_ids: Sequence[int] | None) -> list[int] | None:
    if listing_ids is None:
        return None
    normalized = sorted({int(value) for value in listing_ids})
    return None if not normalized else normalized



def _query_rows(clickhouse_client: object, sql: str) -> list[dict[str, object]]:
    result = clickhouse_client.query(sql)
    rows = getattr(result, "result_rows", ()) or ()
    if not rows:
        return []
    if rows and isinstance(rows[0], Mapping):
        return [{str(key): _normalize_value(value) for key, value in dict(row).items()} for row in rows]
    column_names = getattr(result, "column_names", None)
    if not column_names:
        raise RuntimeError("ClickHouse query result is missing column_names.")
    normalized_column_names = [str(name) for name in column_names]
    return [
        {
            normalized_column_names[index]: _normalize_value(value)
            for index, value in enumerate(row)
        }
        for row in rows
    ]



def _normalize_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_value(item) for item in value)
    return value



def _generated_at(now: str | None) -> str:
    if now is None:
        return datetime.now(UTC).replace(microsecond=0).isoformat()
    return datetime.fromisoformat(now).replace(microsecond=0).isoformat()



def _safe_identifier(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned or _IDENTIFIER_RE.fullmatch(cleaned) is None:
        raise ValueError(f"{field_name} must be a valid ClickHouse identifier.")
    return cleaned



def _safe_date(value: str, *, field_name: str) -> str:
    try:
        return datetime.fromisoformat(str(value)).date().isoformat() if "T" in str(value) else datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD).") from exc



def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"



def _load_json_object(value: object) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}



def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)] if str(value) else []



def _marker_listing_ids(listing_ids: Sequence[int] | None) -> str:
    normalized = _normalize_listing_ids(listing_ids)
    return "all" if normalized is None else ",".join(str(value) for value in normalized)



def _marker_date(value: str | None) -> str:
    return "*" if value is None else _safe_date(value, field_name="date")



def _delta(previous: object, current: object) -> int | None:
    if previous is None or current is None:
        return None
    return int(current) - int(previous)



def _price_band_fields(price_amount_cents: object) -> dict[str, object]:
    if price_amount_cents is None:
        return {"price_band_code": "unknown", "price_band_label": _PRICE_BAND_LABELS["unknown"]}
    amount = int(price_amount_cents)
    if amount < 2000:
        code = "under_20_eur"
    elif amount < 4000:
        code = "20_to_39_eur"
    else:
        code = "40_plus_eur"
    return {"price_band_code": code, "price_band_label": _PRICE_BAND_LABELS[code]}


__all__ = [
    "fetch_clickhouse_listing_day_mart",
    "fetch_clickhouse_price_change_mart",
    "fetch_clickhouse_segment_day_mart",
    "fetch_clickhouse_state_transition_mart",
    "load_clickhouse_evidence_packs",
    "load_clickhouse_feature_marts_export",
]
