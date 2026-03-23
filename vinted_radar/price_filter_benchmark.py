from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from vinted_radar.http import VintedHttpClient
from vinted_radar.models import CatalogNode
from vinted_radar.parsers.api_catalog_page import parse_api_catalog_page
from vinted_radar.parsers.catalog_tree import parse_catalog_tree_from_html
from vinted_radar.services.discovery import (
    ROOT_SCOPE_MAP,
    _build_api_catalog_url,
    _measure_page_scan_telemetry,
    _price_floor_cents,
    _price_limit_cents,
    _select_leaf_catalogs,
)

BenchmarkMode = Literal["bounded", "unbounded"]
ModeOrderStrategy = Literal["alternate", "bounded-first", "unbounded-first"]

_VINTED_CATALOG_ROOT_URL = "https://www.vinted.fr/catalog"
_CHALLENGE_MARKERS = (
    "captcha",
    "challenge",
    "turnstile",
    "cloudflare",
    "attention required",
    "just a moment",
    "__cf_chl",
)


@dataclass(frozen=True, slots=True)
class PriceFilterBenchmarkOptions:
    page_limit: int = 3
    max_leaf_categories: int | None = 10
    root_scope: str = "both"
    request_delay: float = 3.0
    timeout_seconds: float = 20.0
    http_max_retries: int = 1
    min_price: float = 30.0
    max_price: float = 0.0
    target_catalogs: tuple[int, ...] = ()
    proxies: tuple[str, ...] = ()
    mode_order: ModeOrderStrategy = "alternate"


@dataclass(frozen=True, slots=True)
class BenchmarkCatalogSelection:
    catalog_id: int
    root_catalog_id: int
    root_title: str
    title: str
    path_text: str
    url: str


@dataclass(frozen=True, slots=True)
class BenchmarkPageRecord:
    pair_index: int
    mode: BenchmarkMode
    catalog_id: int
    catalog_path: str
    root_title: str
    page_number: int
    requested_url: str
    requested_at: str
    duration_ms: int
    response_status: int | None
    success: bool
    api_listing_count: int | None
    accepted_listing_count: int | None
    filtered_out_count: int | None
    accepted_ratio: float | None
    min_price_seen_cents: int | None
    max_price_seen_cents: int | None
    pagination_total_pages: int | None
    error_kind: str | None
    error_message: str | None
    challenge_suspected: bool


@dataclass(frozen=True, slots=True)
class _ModeRequestPlan:
    mode: BenchmarkMode
    api_price_from: float
    api_price_to: float


def run_price_filter_benchmark(
    options: PriceFilterBenchmarkOptions,
    *,
    http_client: VintedHttpClient | None = None,
) -> dict[str, object]:
    _validate_options(options)
    client = http_client or VintedHttpClient(
        request_delay=options.request_delay,
        timeout_seconds=options.timeout_seconds,
        proxies=list(options.proxies) if options.proxies else None,
        max_retries=options.http_max_retries,
    )
    owns_client = http_client is None

    try:
        root_page = client.get_text(_VINTED_CATALOG_ROOT_URL)
        if root_page.status_code >= 400:
            raise RuntimeError(
                f"Catalog root request failed with HTTP {root_page.status_code}"
            )

        catalogs = parse_catalog_tree_from_html(
            root_page.text,
            allowed_root_titles=set(ROOT_SCOPE_MAP[options.root_scope]),
        )
        selected_catalogs = _select_leaf_catalogs(
            catalogs=catalogs,
            root_titles=ROOT_SCOPE_MAP[options.root_scope],
            limit=options.max_leaf_categories,
            target_catalogs=options.target_catalogs,
        )
        if not selected_catalogs:
            raise RuntimeError("No leaf catalogs matched the benchmark selection.")

        minimum_price_cents = _price_floor_cents(options.min_price)
        maximum_price_cents = _price_limit_cents(options.max_price)
        page_records: list[BenchmarkPageRecord] = []
        pair_index = 0

        for catalog in selected_catalogs:
            for page_number in range(1, options.page_limit + 1):
                pair_index += 1
                pair_records: list[BenchmarkPageRecord] = []
                for request_plan in _mode_request_plan(pair_index, options):
                    record = _fetch_benchmark_page(
                        client=client,
                        catalog=catalog,
                        page_number=page_number,
                        pair_index=pair_index,
                        request_plan=request_plan,
                        minimum_price_cents=minimum_price_cents,
                        maximum_price_cents=maximum_price_cents,
                    )
                    page_records.append(record)
                    pair_records.append(record)

                if any(not record.success for record in pair_records):
                    break
                if all((record.api_listing_count or 0) == 0 for record in pair_records):
                    break

        return build_price_filter_benchmark_report(
            options=options,
            selected_catalogs=selected_catalogs,
            page_records=page_records,
        )
    finally:
        if owns_client:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def build_price_filter_benchmark_report(
    *,
    options: PriceFilterBenchmarkOptions,
    selected_catalogs: list[CatalogNode],
    page_records: list[BenchmarkPageRecord],
) -> dict[str, object]:
    generated_at = _utc_now()
    benchmark_id = f"price-filter-benchmark-{_timestamp_slug(generated_at)}"
    mode_summaries = {
        mode: _summarize_mode_records(
            [record for record in page_records if record.mode == mode]
        )
        for mode in ("bounded", "unbounded")
    }
    paired_pages = _build_paired_pages(page_records)
    report = {
        "benchmark_id": benchmark_id,
        "generated_at": generated_at,
        "config": {
            "root_scope": options.root_scope,
            "page_limit": options.page_limit,
            "max_leaf_categories": options.max_leaf_categories,
            "target_catalogs": list(options.target_catalogs),
            "request_delay": options.request_delay,
            "timeout_seconds": options.timeout_seconds,
            "http_max_retries": options.http_max_retries,
            "mode_order": options.mode_order,
            "page_window_strategy": "fixed_requested_window_with_early_stop_on_hard_failure_or_dual_empty_page",
            "mode_definitions": {
                "bounded": {
                    "api_price_from": options.min_price,
                    "api_price_to": options.max_price,
                    "local_price_from": options.min_price,
                    "local_price_to": options.max_price,
                },
                "unbounded": {
                    "api_price_from": 0.0,
                    "api_price_to": 0.0,
                    "local_price_from": options.min_price,
                    "local_price_to": options.max_price,
                },
            },
        },
        "catalogs": [
            {
                "catalog_id": catalog.catalog_id,
                "root_catalog_id": catalog.root_catalog_id,
                "root_title": catalog.root_title,
                "title": catalog.title,
                "path": catalog.path_text,
                "url": catalog.url,
            }
            for catalog in selected_catalogs
        ],
        "pages": [asdict(record) for record in page_records],
        "aggregates": {
            "by_mode": mode_summaries,
            "delta": _build_mode_delta(mode_summaries),
            "paired_pages": paired_pages,
            "paired_delta_summary": _summarize_paired_pages(paired_pages),
            "by_catalog": _build_catalog_summaries(selected_catalogs, page_records),
        },
    }
    return report


def render_price_filter_benchmark_markdown(report: dict[str, object]) -> str:
    config = dict(report.get("config") or {})
    aggregates = dict(report.get("aggregates") or {})
    by_mode = dict(aggregates.get("by_mode") or {})
    delta = dict(aggregates.get("delta") or {})
    by_catalog = list(aggregates.get("by_catalog") or [])

    lines = [
        f"# Price filter benchmark — {report.get('benchmark_id')}",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "## Method",
        "",
        f"- Root scope: `{config.get('root_scope')}`",
        f"- Catalogs selected: `{len(list(report.get('catalogs') or []))}`",
        f"- Requested page window per catalog: `{config.get('page_limit')}` pages",
        f"- Request delay: `{config.get('request_delay')}` seconds | timeout `{config.get('timeout_seconds')}` seconds | HTTP max retries `{config.get('http_max_retries')}`",
        f"- Local acceptance window: `price_from={config.get('mode_definitions', {}).get('bounded', {}).get('local_price_from')}` `price_to={config.get('mode_definitions', {}).get('bounded', {}).get('local_price_to')}`",
        f"- Mode order: `{config.get('mode_order')}`",
        f"- Page window strategy: `{config.get('page_window_strategy')}`",
        "",
        "## Aggregate comparison",
        "",
        "| Mode | Requests | Success | Failures | Challenge suspects | Mean accepted ratio* | Weighted accepted ratio | Accepted / request | Estimated requests / 100 accepted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in ("bounded", "unbounded"):
        summary = dict(by_mode.get(mode) or {})
        lines.append(
            "| {mode} | {requests} | {success} | {failures} | {challenges} | {mean_ratio} | {weighted_ratio} | {per_request} | {requests_per_100} |".format(
                mode=mode,
                requests=summary.get("request_count", 0),
                success=summary.get("success_count", 0),
                failures=summary.get("failure_count", 0),
                challenges=summary.get("challenge_suspected_count", 0),
                mean_ratio=_format_ratio(summary.get("accepted_ratio_mean")),
                weighted_ratio=_format_ratio(summary.get("accepted_ratio_weighted")),
                per_request=_format_ratio(summary.get("accepted_listings_per_request")),
                requests_per_100=_format_ratio(summary.get("estimated_requests_per_100_accepted_listings")),
            )
        )

    lines.extend(
        [
            "",
            "* Mean accepted ratio is computed over successful non-empty pages only. Empty pages still penalize `accepted_listings_per_request`.",
            "",
            "## Delta (bounded - unbounded)",
            "",
            f"- Mean accepted ratio delta: `{_format_ratio(delta.get('accepted_ratio_mean_delta'))}`",
            f"- Weighted accepted ratio delta: `{_format_ratio(delta.get('accepted_ratio_weighted_delta'))}`",
            f"- Accepted listings per request delta: `{_format_ratio(delta.get('accepted_listings_per_request_delta'))}`",
            f"- Estimated requests per 100 accepted delta: `{_format_ratio(delta.get('estimated_requests_per_100_accepted_listings_delta'))}`",
            f"- Challenge suspected count delta: `{delta.get('challenge_suspected_count_delta')}`",
            "",
            "## Per-catalog summary",
            "",
            "| Catalog | Bounded accepted/request | Unbounded accepted/request | Delta | Bounded weighted ratio | Unbounded weighted ratio |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )

    for item in by_catalog:
        bounded = dict(item.get("bounded") or {})
        unbounded = dict(item.get("unbounded") or {})
        delta_payload = dict(item.get("delta") or {})
        lines.append(
            "| {catalog} | {bounded_per_request} | {unbounded_per_request} | {delta_per_request} | {bounded_ratio} | {unbounded_ratio} |".format(
                catalog=item.get("catalog_path") or item.get("catalog_id"),
                bounded_per_request=_format_ratio(
                    bounded.get("accepted_listings_per_request")
                ),
                unbounded_per_request=_format_ratio(
                    unbounded.get("accepted_listings_per_request")
                ),
                delta_per_request=_format_ratio(
                    delta_payload.get("accepted_listings_per_request_delta")
                ),
                bounded_ratio=_format_ratio(
                    bounded.get("accepted_ratio_weighted")
                ),
                unbounded_ratio=_format_ratio(
                    unbounded.get("accepted_ratio_weighted")
                ),
            )
        )

    return "\n".join(lines) + "\n"


def write_price_filter_benchmark_report(
    report: dict[str, object],
    *,
    json_path: str | Path,
    markdown_path: str | Path | None = None,
) -> dict[str, str]:
    json_target = Path(json_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    written = {"json": str(json_target)}
    if markdown_path is not None:
        markdown_target = Path(markdown_path)
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        markdown_target.write_text(
            render_price_filter_benchmark_markdown(report),
            encoding="utf-8",
        )
        written["markdown"] = str(markdown_target)
    return written


def _validate_options(options: PriceFilterBenchmarkOptions) -> None:
    if options.root_scope not in ROOT_SCOPE_MAP:
        raise ValueError(f"Unsupported root scope: {options.root_scope}")
    if options.page_limit < 1:
        raise ValueError("page_limit must be at least 1")
    if options.min_price < 0:
        raise ValueError("min_price must be at least 0")
    if options.max_price < 0:
        raise ValueError("max_price must be at least 0")
    if options.http_max_retries < 1:
        raise ValueError("http_max_retries must be at least 1")
    if options.mode_order not in {"alternate", "bounded-first", "unbounded-first"}:
        raise ValueError(f"Unsupported mode order: {options.mode_order}")


def _mode_request_plan(
    pair_index: int,
    options: PriceFilterBenchmarkOptions,
) -> tuple[_ModeRequestPlan, _ModeRequestPlan]:
    bounded = _ModeRequestPlan(
        mode="bounded",
        api_price_from=options.min_price,
        api_price_to=options.max_price,
    )
    unbounded = _ModeRequestPlan(
        mode="unbounded",
        api_price_from=0.0,
        api_price_to=0.0,
    )
    if options.mode_order == "bounded-first":
        return (bounded, unbounded)
    if options.mode_order == "unbounded-first":
        return (unbounded, bounded)
    if pair_index % 2 == 1:
        return (bounded, unbounded)
    return (unbounded, bounded)


def _fetch_benchmark_page(
    *,
    client: VintedHttpClient,
    catalog: CatalogNode,
    page_number: int,
    pair_index: int,
    request_plan: _ModeRequestPlan,
    minimum_price_cents: int,
    maximum_price_cents: int,
) -> BenchmarkPageRecord:
    requested_url = _build_api_catalog_url(
        catalog.catalog_id,
        page_number,
        price_from=request_plan.api_price_from,
        price_to=request_plan.api_price_to,
    )
    requested_at = _utc_now()
    started_at = time.monotonic()

    try:
        page = client.get_text(requested_url)
        duration_ms = _duration_ms(started_at)
        if page.status_code >= 400:
            return BenchmarkPageRecord(
                pair_index=pair_index,
                mode=request_plan.mode,
                catalog_id=catalog.catalog_id,
                catalog_path=catalog.path_text,
                root_title=catalog.root_title,
                page_number=page_number,
                requested_url=requested_url,
                requested_at=requested_at,
                duration_ms=duration_ms,
                response_status=page.status_code,
                success=False,
                api_listing_count=None,
                accepted_listing_count=None,
                filtered_out_count=None,
                accepted_ratio=None,
                min_price_seen_cents=None,
                max_price_seen_cents=None,
                pagination_total_pages=None,
                error_kind=_http_error_kind(page.status_code),
                error_message=f"HTTP {page.status_code}",
                challenge_suspected=_challenge_suspected(
                    page.status_code,
                    page.text,
                ),
            )

        try:
            payload = json.loads(page.text)
        except json.JSONDecodeError as exc:
            challenge_suspected = _challenge_suspected(page.status_code, page.text)
            return BenchmarkPageRecord(
                pair_index=pair_index,
                mode=request_plan.mode,
                catalog_id=catalog.catalog_id,
                catalog_path=catalog.path_text,
                root_title=catalog.root_title,
                page_number=page_number,
                requested_url=requested_url,
                requested_at=requested_at,
                duration_ms=duration_ms,
                response_status=page.status_code,
                success=False,
                api_listing_count=None,
                accepted_listing_count=None,
                filtered_out_count=None,
                accepted_ratio=None,
                min_price_seen_cents=None,
                max_price_seen_cents=None,
                pagination_total_pages=None,
                error_kind=(
                    "invalid_json_challenge"
                    if challenge_suspected
                    else "invalid_json_non_json"
                ),
                error_message=f"JSONDecodeError: {exc}",
                challenge_suspected=challenge_suspected,
            )

        parsed_page = parse_api_catalog_page(
            payload,
            source_catalog_id=catalog.catalog_id,
            source_root_catalog_id=catalog.root_catalog_id,
        )
        telemetry = _measure_page_scan_telemetry(
            parsed_page.listings,
            minimum_price_cents=minimum_price_cents,
            maximum_price_cents=maximum_price_cents,
            target_brands=frozenset(),
        )
        return BenchmarkPageRecord(
            pair_index=pair_index,
            mode=request_plan.mode,
            catalog_id=catalog.catalog_id,
            catalog_path=catalog.path_text,
            root_title=catalog.root_title,
            page_number=page_number,
            requested_url=requested_url,
            requested_at=requested_at,
            duration_ms=duration_ms,
            response_status=page.status_code,
            success=True,
            api_listing_count=telemetry.api_listing_count,
            accepted_listing_count=telemetry.accepted_listing_count,
            filtered_out_count=telemetry.filtered_out_count,
            accepted_ratio=telemetry.accepted_ratio,
            min_price_seen_cents=telemetry.min_price_seen_cents,
            max_price_seen_cents=telemetry.max_price_seen_cents,
            pagination_total_pages=parsed_page.total_pages,
            error_kind=None,
            error_message=None,
            challenge_suspected=False,
        )
    except Exception as exc:  # noqa: BLE001
        return BenchmarkPageRecord(
            pair_index=pair_index,
            mode=request_plan.mode,
            catalog_id=catalog.catalog_id,
            catalog_path=catalog.path_text,
            root_title=catalog.root_title,
            page_number=page_number,
            requested_url=requested_url,
            requested_at=requested_at,
            duration_ms=_duration_ms(started_at),
            response_status=None,
            success=False,
            api_listing_count=None,
            accepted_listing_count=None,
            filtered_out_count=None,
            accepted_ratio=None,
            min_price_seen_cents=None,
            max_price_seen_cents=None,
            pagination_total_pages=None,
            error_kind="transport_error",
            error_message=f"{type(exc).__name__}: {exc}",
            challenge_suspected=False,
        )


def _build_paired_pages(
    page_records: list[BenchmarkPageRecord],
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], dict[str, object]] = {}
    for record in page_records:
        key = (record.catalog_id, record.page_number)
        payload = grouped.setdefault(
            key,
            {
                "catalog_id": record.catalog_id,
                "catalog_path": record.catalog_path,
                "root_title": record.root_title,
                "page_number": record.page_number,
                "pair_index": record.pair_index,
            },
        )
        payload[record.mode] = asdict(record)

    paired_pages: list[dict[str, object]] = []
    for key in sorted(grouped):
        payload = grouped[key]
        bounded = payload.get("bounded")
        unbounded = payload.get("unbounded")
        if isinstance(bounded, dict) and isinstance(unbounded, dict):
            payload["delta"] = {
                "accepted_listing_count_delta": _subtract_nullable(
                    bounded.get("accepted_listing_count"),
                    unbounded.get("accepted_listing_count"),
                ),
                "filtered_out_count_delta": _subtract_nullable(
                    bounded.get("filtered_out_count"),
                    unbounded.get("filtered_out_count"),
                ),
                "accepted_ratio_delta": _subtract_nullable(
                    bounded.get("accepted_ratio"),
                    unbounded.get("accepted_ratio"),
                ),
                "success_delta": int(bool(bounded.get("success")))
                - int(bool(unbounded.get("success"))),
                "challenge_suspected_delta": int(
                    bool(bounded.get("challenge_suspected"))
                )
                - int(bool(unbounded.get("challenge_suspected"))),
            }
        paired_pages.append(payload)
    return paired_pages


def _summarize_paired_pages(
    paired_pages: list[dict[str, object]],
) -> dict[str, object]:
    comparable_pairs = [
        item
        for item in paired_pages
        if isinstance(item.get("bounded"), dict)
        and isinstance(item.get("unbounded"), dict)
    ]
    accepted_ratio_deltas = [
        item["delta"]["accepted_ratio_delta"]
        for item in comparable_pairs
        if isinstance(item.get("delta"), dict)
        and item["delta"].get("accepted_ratio_delta") is not None
    ]
    accepted_listing_count_deltas = [
        item["delta"]["accepted_listing_count_delta"]
        for item in comparable_pairs
        if isinstance(item.get("delta"), dict)
        and item["delta"].get("accepted_listing_count_delta") is not None
    ]
    return {
        "comparable_pair_count": len(comparable_pairs),
        "accepted_ratio_delta_mean": _mean_or_none(accepted_ratio_deltas),
        "accepted_ratio_delta_median": _median_or_none(accepted_ratio_deltas),
        "accepted_ratio_delta_min": _min_or_none(accepted_ratio_deltas),
        "accepted_ratio_delta_max": _max_or_none(accepted_ratio_deltas),
        "accepted_ratio_delta_positive_pairs": sum(
            1 for value in accepted_ratio_deltas if value > 0
        ),
        "accepted_ratio_delta_negative_pairs": sum(
            1 for value in accepted_ratio_deltas if value < 0
        ),
        "accepted_ratio_delta_zero_pairs": sum(
            1 for value in accepted_ratio_deltas if value == 0
        ),
        "accepted_listing_count_delta_mean": _mean_or_none(
            accepted_listing_count_deltas
        ),
        "accepted_listing_count_delta_median": _median_or_none(
            accepted_listing_count_deltas
        ),
        "accepted_listing_count_delta_min": _min_or_none(
            accepted_listing_count_deltas
        ),
        "accepted_listing_count_delta_max": _max_or_none(
            accepted_listing_count_deltas
        ),
    }


def _build_catalog_summaries(
    selected_catalogs: list[CatalogNode],
    page_records: list[BenchmarkPageRecord],
) -> list[dict[str, object]]:
    records_by_catalog: dict[int, list[BenchmarkPageRecord]] = defaultdict(list)
    for record in page_records:
        records_by_catalog[record.catalog_id].append(record)

    summaries: list[dict[str, object]] = []
    for catalog in selected_catalogs:
        catalog_records = records_by_catalog.get(catalog.catalog_id, [])
        bounded_records = [
            record for record in catalog_records if record.mode == "bounded"
        ]
        unbounded_records = [
            record for record in catalog_records if record.mode == "unbounded"
        ]
        bounded_summary = _summarize_mode_records(bounded_records)
        unbounded_summary = _summarize_mode_records(unbounded_records)
        summaries.append(
            {
                "catalog_id": catalog.catalog_id,
                "catalog_path": catalog.path_text,
                "root_title": catalog.root_title,
                "bounded": bounded_summary,
                "unbounded": unbounded_summary,
                "delta": _build_mode_delta(
                    {
                        "bounded": bounded_summary,
                        "unbounded": unbounded_summary,
                    }
                ),
            }
        )
    return summaries


def _summarize_mode_records(
    records: list[BenchmarkPageRecord],
) -> dict[str, object]:
    request_count = len(records)
    success_records = [record for record in records if record.success]
    non_empty_success_records = [
        record
        for record in success_records
        if (record.api_listing_count or 0) > 0
    ]
    accepted_ratio_values = [
        record.accepted_ratio
        for record in non_empty_success_records
        if record.accepted_ratio is not None
    ]
    accepted_listing_count_total = sum(record.accepted_listing_count or 0 for record in records)
    api_listing_count_total = sum(record.api_listing_count or 0 for record in success_records)
    filtered_out_count_total = sum(record.filtered_out_count or 0 for record in success_records)
    accepted_listings_per_request = (
        accepted_listing_count_total / request_count if request_count else None
    )
    estimated_requests_per_100 = (
        None
        if accepted_listings_per_request in {None, 0}
        else 100.0 / accepted_listings_per_request
    )
    response_status_counts = Counter(
        "null" if record.response_status is None else str(record.response_status)
        for record in records
    )
    return {
        "request_count": request_count,
        "success_count": len(success_records),
        "failure_count": request_count - len(success_records),
        "success_rate": None if request_count == 0 else len(success_records) / request_count,
        "non_empty_page_count": len(non_empty_success_records),
        "empty_page_count": sum(
            1 for record in success_records if (record.api_listing_count or 0) == 0
        ),
        "accepted_ratio_samples": len(accepted_ratio_values),
        "accepted_ratio_mean": _mean_or_none(accepted_ratio_values),
        "accepted_ratio_median": _median_or_none(accepted_ratio_values),
        "accepted_ratio_min": _min_or_none(accepted_ratio_values),
        "accepted_ratio_max": _max_or_none(accepted_ratio_values),
        "accepted_ratio_weighted": (
            None
            if api_listing_count_total == 0
            else accepted_listing_count_total / api_listing_count_total
        ),
        "api_listing_count_total": api_listing_count_total,
        "accepted_listing_count_total": accepted_listing_count_total,
        "filtered_out_count_total": filtered_out_count_total,
        "accepted_listings_per_request": accepted_listings_per_request,
        "estimated_requests_per_100_accepted_listings": estimated_requests_per_100,
        "challenge_suspected_count": sum(
            1 for record in records if record.challenge_suspected
        ),
        "http_403_count": sum(1 for record in records if record.response_status == 403),
        "http_429_count": sum(1 for record in records if record.response_status == 429),
        "http_error_count": sum(
            1
            for record in records
            if record.response_status is not None and record.response_status >= 400
        ),
        "invalid_json_count": sum(
            1
            for record in records
            if record.error_kind in {"invalid_json_challenge", "invalid_json_non_json"}
        ),
        "transport_error_count": sum(
            1 for record in records if record.error_kind == "transport_error"
        ),
        "response_status_counts": dict(sorted(response_status_counts.items())),
    }


def _build_mode_delta(
    mode_summaries: dict[str, dict[str, object]],
) -> dict[str, object]:
    bounded = dict(mode_summaries.get("bounded") or {})
    unbounded = dict(mode_summaries.get("unbounded") or {})
    bounded_per_request = bounded.get("accepted_listings_per_request")
    unbounded_per_request = unbounded.get("accepted_listings_per_request")
    bounded_requests_per_100 = bounded.get("estimated_requests_per_100_accepted_listings")
    unbounded_requests_per_100 = unbounded.get("estimated_requests_per_100_accepted_listings")
    return {
        "accepted_ratio_mean_delta": _subtract_nullable(
            bounded.get("accepted_ratio_mean"),
            unbounded.get("accepted_ratio_mean"),
        ),
        "accepted_ratio_median_delta": _subtract_nullable(
            bounded.get("accepted_ratio_median"),
            unbounded.get("accepted_ratio_median"),
        ),
        "accepted_ratio_weighted_delta": _subtract_nullable(
            bounded.get("accepted_ratio_weighted"),
            unbounded.get("accepted_ratio_weighted"),
        ),
        "accepted_listings_per_request_delta": _subtract_nullable(
            bounded_per_request,
            unbounded_per_request,
        ),
        "accepted_listings_per_request_relative_change_pct": _relative_change_pct(
            baseline=unbounded_per_request,
            candidate=bounded_per_request,
        ),
        "estimated_requests_per_100_accepted_listings_delta": _subtract_nullable(
            bounded_requests_per_100,
            unbounded_requests_per_100,
        ),
        "estimated_requests_per_100_accepted_listings_relative_change_pct": _relative_change_pct(
            baseline=unbounded_requests_per_100,
            candidate=bounded_requests_per_100,
        ),
        "success_rate_delta": _subtract_nullable(
            bounded.get("success_rate"),
            unbounded.get("success_rate"),
        ),
        "challenge_suspected_count_delta": int(
            bounded.get("challenge_suspected_count") or 0
        )
        - int(unbounded.get("challenge_suspected_count") or 0),
        "http_error_count_delta": int(bounded.get("http_error_count") or 0)
        - int(unbounded.get("http_error_count") or 0),
        "accepted_listing_count_total_delta": int(
            bounded.get("accepted_listing_count_total") or 0
        )
        - int(unbounded.get("accepted_listing_count_total") or 0),
    }


def _http_error_kind(status_code: int) -> str:
    if status_code == 403:
        return "http_403"
    if status_code == 429:
        return "http_429"
    return "http_error"


def _challenge_suspected(status_code: int | None, text: str | None) -> bool:
    if status_code in {403, 429}:
        return True
    if not text:
        return False
    lowered = text.casefold()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def _duration_ms(started_at: float) -> int:
    return int(round((time.monotonic() - started_at) * 1000.0))


def _subtract_nullable(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def _relative_change_pct(*, baseline: object, candidate: object) -> float | None:
    if baseline is None or candidate is None:
        return None
    baseline_value = float(baseline)
    candidate_value = float(candidate)
    if baseline_value == 0:
        return None
    return ((candidate_value - baseline_value) / baseline_value) * 100.0


def _mean_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return statistics.fmean(float(value) for value in values)


def _median_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(statistics.median(float(value) for value in values))


def _min_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(min(values))


def _max_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(max(values))


def _format_ratio(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _timestamp_slug(value: str) -> str:
    return value.replace(":", "").replace("+00:00", "Z")
