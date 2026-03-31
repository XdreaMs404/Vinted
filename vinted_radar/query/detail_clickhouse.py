from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import json
import re

from vinted_radar.card_payload import normalize_card_snapshot

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def fetch_clickhouse_state_inputs(
    clickhouse_client: object,
    *,
    database: str,
    listing_id: int | None = None,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    filter_sql = "" if listing_id is None else f"WHERE listing_id = {int(listing_id)}"
    marker_listing_id = "all" if listing_id is None else str(int(listing_id))
    sql = f"""
    /* clickhouse-query: state-inputs listing_id={marker_listing_id} */
    WITH observation_rows AS (
        SELECT
            listing_id,
            ifNull(run_id, event_id) AS observation_key,
            max(observed_at) AS observed_at,
            count() AS sighting_count
        FROM {safe_database}.fact_listing_seen_events
        {filter_sql}
        GROUP BY listing_id, observation_key
    ),
    summary AS (
        SELECT
            listing_id,
            count() AS observation_count,
            sum(sighting_count) AS total_sightings,
            min(observed_at) AS first_seen_at,
            max(observed_at) AS last_seen_at,
            argMax(observation_key, observed_at) AS last_observed_run_id,
            arraySort(groupUniqArray(observation_key)) AS seen_run_ids,
            arraySort(groupArray(observed_at)) AS observed_points
        FROM observation_rows
        GROUP BY listing_id
    )
    SELECT
        summary.listing_id,
        summary.observation_count,
        summary.total_sightings,
        summary.first_seen_at,
        summary.last_seen_at,
        if(
            length(summary.observed_points) < 2,
            CAST(NULL AS Nullable(Float64)),
            round(
                arrayAvg(
                    arrayMap(
                        (current_point, previous_point) -> dateDiff('second', previous_point, current_point) / 3600.0,
                        arrayPopFront(summary.observed_points),
                        arrayPopBack(summary.observed_points)
                    )
                ),
                2
            )
        ) AS average_revisit_hours,
        summary.last_observed_run_id,
        summary.seen_run_ids,
        latest_seen.canonical_url,
        latest_seen.source_url,
        latest_seen.title,
        latest_seen.brand,
        latest_seen.size_label,
        latest_seen.condition_label,
        latest_seen.price_amount_cents,
        latest_seen.price_currency,
        latest_seen.total_price_amount_cents,
        latest_seen.total_price_currency,
        latest_seen.image_url,
        latest_seen.favourite_count,
        latest_seen.view_count,
        latest_seen.user_id,
        latest_seen.user_login,
        latest_seen.user_profile_url,
        latest_seen.created_at_ts,
        latest_seen.root_title,
        latest_seen.primary_catalog_id,
        latest_seen.primary_root_catalog_id,
        latest_seen.category_path AS primary_catalog_path,
        latest_probe.probed_at AS latest_probe_probed_at,
        latest_probe.requested_url AS latest_probe_requested_url,
        latest_probe.final_url AS latest_probe_final_url,
        latest_probe.response_status AS latest_probe_response_status,
        latest_probe.probe_outcome AS latest_probe_outcome,
        latest_probe.detail_json AS latest_probe_detail_json,
        latest_probe.error_message AS latest_probe_error_message
    FROM summary
    INNER JOIN {safe_database}.serving_listing_latest_seen FINAL AS latest_seen
        ON latest_seen.listing_id = summary.listing_id
    LEFT JOIN {safe_database}.serving_listing_latest_probe FINAL AS latest_probe
        ON latest_probe.listing_id = summary.listing_id
    ORDER BY summary.last_seen_at DESC, summary.listing_id DESC
    """
    return _query_rows(clickhouse_client, sql)


def fetch_clickhouse_listing_timeline(
    clickhouse_client: object,
    *,
    database: str,
    listing_id: int,
    limit: int,
) -> list[dict[str, object]]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    safe_listing_id = int(listing_id)
    safe_limit = max(int(limit), 1)
    sql = f"""
    /* clickhouse-query: timeline listing_id={safe_listing_id} limit={safe_limit} */
    SELECT
        ifNull(run_id, event_id) AS run_id,
        listing_id,
        max(observed_at) AS observed_at,
        argMax(canonical_url, observed_at) AS canonical_url,
        argMax(source_url, observed_at) AS source_url,
        argMax(source_catalog_id, observed_at) AS source_catalog_id,
        argMax(source_page_number, observed_at) AS source_page_number,
        argMax(card_position, observed_at) AS first_card_position,
        count() AS sighting_count,
        argMax(title, observed_at) AS title,
        argMax(brand, observed_at) AS brand,
        argMax(size_label, observed_at) AS size_label,
        argMax(condition_label, observed_at) AS condition_label,
        argMax(price_amount_cents, observed_at) AS price_amount_cents,
        argMax(price_currency, observed_at) AS price_currency,
        argMax(total_price_amount_cents, observed_at) AS total_price_amount_cents,
        argMax(total_price_currency, observed_at) AS total_price_currency,
        argMax(image_url, observed_at) AS image_url,
        argMax(raw_card_json, observed_at) AS raw_card_payload_json,
        argMax(category_path, observed_at) AS catalog_path,
        argMax(root_title, observed_at) AS root_title
    FROM {safe_database}.fact_listing_seen_events
    WHERE listing_id = {safe_listing_id}
    GROUP BY listing_id, ifNull(run_id, event_id)
    ORDER BY observed_at DESC, run_id DESC
    LIMIT {safe_limit}
    """
    rows = _query_rows(clickhouse_client, sql)
    return [_hydrate_observation_row(row) for row in rows]


def fetch_clickhouse_price_context_peer_prices(
    clickhouse_client: object,
    *,
    database: str,
    primary_catalog_id: int | None = None,
    root_title: str | None = None,
    brand: str | None = None,
    condition_label: str | None = None,
) -> list[int]:
    safe_database = _safe_identifier(database, field_name="ClickHouse database")
    where_clauses = ["price_amount_cents IS NOT NULL"]
    marker_parts = ["clickhouse-query: peer-prices"]

    if primary_catalog_id is not None:
        safe_catalog_id = int(primary_catalog_id)
        where_clauses.append(f"primary_catalog_id = {safe_catalog_id}")
        marker_parts.append(f"primary_catalog_id={safe_catalog_id}")
    else:
        marker_parts.append("primary_catalog_id=*")

    normalized_root = _norm_text(root_title)
    if normalized_root is not None:
        where_clauses.append(f"lowerUTF8(trimBoth(ifNull(root_title, ''))) = {_sql_string(normalized_root)}")
        marker_parts.append(f"root_title={normalized_root}")
    else:
        marker_parts.append("root_title=*")

    normalized_brand = _norm_text(brand)
    if normalized_brand is not None:
        where_clauses.append(f"lowerUTF8(trimBoth(ifNull(brand, ''))) = {_sql_string(normalized_brand)}")
        marker_parts.append(f"brand={normalized_brand}")
    else:
        marker_parts.append("brand=*")

    normalized_condition = _norm_text(condition_label)
    if normalized_condition is not None:
        where_clauses.append(
            f"lowerUTF8(trimBoth(ifNull(condition_label, ''))) = {_sql_string(normalized_condition)}"
        )
        marker_parts.append(f"condition_label={normalized_condition}")
    else:
        marker_parts.append("condition_label=*")

    sql = f"""
    /* {' '.join(marker_parts)} */
    SELECT price_amount_cents
    FROM {safe_database}.serving_listing_latest_seen FINAL
    WHERE {' AND '.join(where_clauses)}
    ORDER BY listing_id ASC
    """
    rows = _query_rows(clickhouse_client, sql)
    return [int(row["price_amount_cents"]) for row in rows if row.get("price_amount_cents") is not None]


def _hydrate_observation_row(row: Mapping[str, object]) -> dict[str, object]:
    raw_payload = _load_json_object(row.get("raw_card_payload_json"))
    fallback = normalize_card_snapshot(
        raw_card_payload=raw_payload,
        source_url=_optional_str(row.get("source_url")),
        canonical_url=_optional_str(row.get("canonical_url")),
        image_url=_optional_str(row.get("image_url")),
    )
    hydrated = dict(row)
    for field in (
        "canonical_url",
        "title",
        "brand",
        "size_label",
        "condition_label",
        "price_amount_cents",
        "price_currency",
        "total_price_amount_cents",
        "total_price_currency",
        "image_url",
    ):
        if hydrated.get(field) is None:
            hydrated[field] = fallback.get(field)
    hydrated["raw_card"] = raw_payload
    return hydrated


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
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_value(item) for item in value)
    return value


def _safe_identifier(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned or _IDENTIFIER_RE.fullmatch(cleaned) is None:
        raise ValueError(f"{field_name} must be a valid ClickHouse identifier.")
    return cleaned


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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _norm_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


__all__ = [
    "fetch_clickhouse_listing_timeline",
    "fetch_clickhouse_price_context_peer_prices",
    "fetch_clickhouse_state_inputs",
]
