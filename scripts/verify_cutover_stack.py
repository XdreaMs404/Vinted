from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from vinted_radar.dashboard import start_dashboard_server
from vinted_radar.platform import (
    CLICKHOUSE_INGEST_CONSUMER,
    ClickHouseIngestService,
    S3ObjectStore,
    doctor_data_platform,
    load_clickhouse_ingest_status,
    load_platform_config,
    summarize_cutover_state,
    summarize_platform_health,
)
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository
from vinted_radar.query.feature_marts import load_clickhouse_feature_marts_export
from vinted_radar.services.platform_audit import run_platform_audit

try:  # pragma: no cover - import style depends on script entrypoint
    from .verify_clickhouse_routes import verify_clickhouse_routes
    from .verify_vps_serving import VerificationError, verify as verify_vps_serving
except ImportError:  # pragma: no cover - direct script execution path
    from verify_clickhouse_routes import verify_clickhouse_routes
    from verify_vps_serving import VerificationError, verify as verify_vps_serving


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "vinted-radar-cutover-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise VerificationError(f"{url} returned HTTP {exc.code}: {body[:280]}") from exc
    except URLError as exc:
        raise VerificationError(f"failed to reach {url}: {exc.reason}") from exc

    if "application/json" not in content_type:
        raise VerificationError(f"{url} did not return JSON: {content_type}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{url} did not return valid JSON: {exc}") from exc


def _route_url(base_url: str, route: str) -> str:
    normalized = base_url.rstrip("/")
    if route == "/":
        return normalized + "/"
    return normalized + route


def _row_value(row: object, key: str, index: int) -> object:
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "keys"):
        return row[key]
    if isinstance(row, (list, tuple)):
        return row[index]
    raise TypeError(f"Unsupported row type: {type(row).__name__}")


def _resolve_listing_id(repository: PostgresMutableTruthRepository, requested_listing_id: int | None) -> int:
    if requested_listing_id is not None:
        return int(requested_listing_id)
    row = repository.connection.execute(
        "SELECT listing_id FROM platform_listing_current_state ORDER BY projected_at DESC, listing_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise VerificationError("No platform listing current-state row exists yet; cannot choose a representative listing.")
    return int(_row_value(row, "listing_id", 0))


def _non_marker_keys(store: S3ObjectStore, prefix: str) -> list[str]:
    marker_key = prefix.rstrip("/") + "/.prefix"
    return [key for key in store.list_keys(prefix, limit=50) if key != marker_key]


def _drain_clickhouse_ingest(*, max_passes: int = 10, limit: int = 100) -> list[dict[str, Any]]:
    service = ClickHouseIngestService.from_environment(consumer_name=CLICKHOUSE_INGEST_CONSUMER)
    reports: list[dict[str, Any]] = []
    try:
        for _ in range(max_passes):
            report = service.ingest_available(limit=limit, consumer_name=CLICKHOUSE_INGEST_CONSUMER)
            reports.append(report.as_dict())
            if report.claimed_count == 0:
                return reports
    finally:
        service.close()
    raise VerificationError(
        f"ClickHouse ingest still had claimable work after {max_passes} passes; refusing to treat the stack as settled."
    )


def _validate_platform_audit(*, db_path: str | Path, config) -> dict[str, Any]:
    report = run_platform_audit(db_path, config=config)
    payload = report.as_dict()
    summary = dict(payload.get("summary") or {})
    paths = dict(payload.get("paths") or {})

    reconciliation_status = str(summary.get("reconciliation_status") or "unknown")
    if reconciliation_status != "match":
        raise VerificationError(
            f"Platform audit reconciliation drifted to {reconciliation_status!r}; expected 'match' before final acceptance."
        )

    current_state_status = str((paths.get("current_state") or {}).get("status") or "unknown")
    if current_state_status not in {"healthy", "active"}:
        raise VerificationError(
            f"Platform audit current-state path is {current_state_status!r}; expected 'healthy' or 'active'."
        )

    analytical_status = str((paths.get("analytical") or {}).get("status") or "unknown")
    if analytical_status not in {"healthy", "active"}:
        raise VerificationError(
            f"Platform audit analytical path is {analytical_status!r}; expected 'healthy' or 'active'."
        )

    backfill_status = str((paths.get("backfill") or {}).get("status") or "unknown")
    if backfill_status not in {"healthy", "complete"}:
        raise VerificationError(
            f"Platform audit backfill path is {backfill_status!r}; expected 'healthy' or 'complete'."
        )

    lifecycle_status = str((paths.get("lifecycle") or {}).get("status") or "unknown")
    if lifecycle_status == "failed":
        raise VerificationError("Platform audit lifecycle posture failed during the final acceptance proof.")

    return payload


def _collect_change_fact_run_ids(rows: list[dict[str, Any]]) -> list[str]:
    run_ids = {
        str((dict(row.get("trace") or {})).get("run_id"))
        for row in rows
        if (dict(row.get("trace") or {})).get("run_id")
    }
    return sorted(run_ids)


def _choose_evidence_pack(
    evidence_packs: list[dict[str, Any]],
    *,
    representative_listing_id: int,
    preferred_listing_ids: set[int],
) -> dict[str, Any]:
    def _rank(pack: dict[str, Any]) -> tuple[int, int]:
        listing_id = int(pack.get("listing_id") or 0)
        window = dict(pack.get("window") or {})
        change_count = int(window.get("price_change_count") or 0) + int(window.get("state_transition_count") or 0)
        if listing_id in preferred_listing_ids:
            return (0, -change_count)
        if change_count > 0:
            return (1, -change_count)
        if listing_id == representative_listing_id:
            return (2, -change_count)
        return (3, -change_count)

    return sorted(evidence_packs, key=_rank)[0]


def _validate_feature_marts(
    *,
    config,
    latest_discovery_run_id: str | None,
    representative_listing_id: int,
) -> dict[str, Any]:
    clickhouse_client = _get_clickhouse_client(config, database=config.clickhouse.database)
    try:
        export = load_clickhouse_feature_marts_export(
            clickhouse_client,
            database=config.clickhouse.database,
            limit=25,
        )
    finally:
        close = getattr(clickhouse_client, "close", None)
        if callable(close):
            close()

    if str(export.get("source") or "") != "clickhouse.feature_marts":
        raise VerificationError(
            f"Feature-mart export source drifted to {export.get('source')!r} instead of 'clickhouse.feature_marts'."
        )

    listing_day_rows = list((export.get("listing_day") or {}).get("rows") or [])
    segment_day_rows = list((export.get("segment_day") or {}).get("rows") or [])
    price_change_rows = list((export.get("price_change") or {}).get("rows") or [])
    state_transition_rows = list((export.get("state_transition") or {}).get("rows") or [])
    evidence_packs = list((export.get("evidence_packs") or {}).get("rows") or [])
    change_rows = price_change_rows + state_transition_rows

    if not listing_day_rows:
        raise VerificationError("Feature-mart export returned no listing-day rows.")
    if not evidence_packs:
        raise VerificationError("Feature-mart export returned no evidence packs.")
    if not change_rows:
        raise VerificationError("Feature-mart export returned no populated change-fact rows.")

    fresh_change_rows = [
        row
        for row in change_rows
        if str((dict(row.get("trace") or {})).get("run_id") or "") == str(latest_discovery_run_id or "")
    ]
    if latest_discovery_run_id and not fresh_change_rows:
        raise VerificationError(
            "Feature-mart export did not expose a fresh change-fact row for the latest discovery run "
            f"{latest_discovery_run_id!r}."
        )

    fresh_change_listing_ids = {
        int(row.get("listing_id") or 0)
        for row in fresh_change_rows
        if row.get("listing_id") is not None
    }
    evidence_pack = _choose_evidence_pack(
        evidence_packs,
        representative_listing_id=representative_listing_id,
        preferred_listing_ids=fresh_change_listing_ids,
    )
    trace = dict(evidence_pack.get("trace") or {})
    manifest_ids = [str(item) for item in list(trace.get("manifest_ids") or []) if item]
    source_event_ids = [str(item) for item in list(trace.get("source_event_ids") or []) if item]
    run_ids = [str(item) for item in list(trace.get("run_ids") or []) if item]
    inspect_examples = [str(item) for item in list(trace.get("inspect_examples") or []) if item]
    if not manifest_ids:
        raise VerificationError("Feature-mart evidence-pack drill-down is missing manifest trace IDs.")
    if not inspect_examples:
        raise VerificationError("Feature-mart evidence-pack drill-down is missing evidence-inspect examples.")

    latest_change_occurred_at = max((str(row.get("occurred_at")) for row in change_rows if row.get("occurred_at")), default=None)
    return {
        "source": export.get("source"),
        "listing_day_row_count": len(listing_day_rows),
        "segment_day_row_count": len(segment_day_rows),
        "price_change_row_count": len(price_change_rows),
        "state_transition_row_count": len(state_transition_rows),
        "change_fact_row_count": len(change_rows),
        "latest_change_occurred_at": latest_change_occurred_at,
        "change_fact_run_ids": _collect_change_fact_run_ids(change_rows),
        "fresh_change_fact_run_ids": _collect_change_fact_run_ids(fresh_change_rows),
        "fresh_change_fact_listing_ids": sorted(fresh_change_listing_ids),
        "evidence_pack_row_count": len(evidence_packs),
        "evidence_drill_down": {
            "listing_id": int(evidence_pack.get("listing_id") or 0),
            "price_change_count": int((dict(evidence_pack.get("window") or {})).get("price_change_count") or 0),
            "state_transition_count": int((dict(evidence_pack.get("window") or {})).get("state_transition_count") or 0),
            "manifest_ids": manifest_ids[:3],
            "source_event_ids": source_event_ids[:3],
            "run_ids": run_ids[:3],
            "inspect_examples": inspect_examples[:3],
        },
    }


def verify_cutover_stack(
    *,
    db_path: str | Path,
    listing_id: int | None,
    base_url: str | None,
    timeout: float,
    host: str,
    port: int,
    expected_cutover_mode: str = "polyglot-cutover",
) -> dict[str, Any]:
    config = load_platform_config()
    cutover = summarize_cutover_state(config)
    if cutover.mode != expected_cutover_mode:
        raise VerificationError(
            f"Cutover mode is {cutover.mode!r}; expected {expected_cutover_mode!r} before running the live smoke proof."
        )

    doctor_report = doctor_data_platform(config=config)
    doctor_snapshot = summarize_platform_health(doctor_report)
    if not doctor_snapshot.ok:
        raise VerificationError(
            "Data-platform doctor is unhealthy: "
            f"postgres={doctor_snapshot.postgres_ok}, "
            f"clickhouse={doctor_snapshot.clickhouse_ok}, "
            f"object_storage={doctor_snapshot.object_storage_ok}"
        )

    ingest_reports = _drain_clickhouse_ingest()
    ingest_status = load_clickhouse_ingest_status(config=config, consumer_name=CLICKHOUSE_INGEST_CONSUMER)
    if ingest_status.status == "failed":
        raise VerificationError(
            f"ClickHouse ingest checkpoint is failed: {ingest_status.last_error or 'unknown error'}"
        )

    repository = PostgresMutableTruthRepository.from_dsn(config.postgres.dsn)
    try:
        representative_listing_id = _resolve_listing_id(repository, listing_id)
        discovery_run = repository.latest_discovery_run()
        if discovery_run is None:
            raise VerificationError("PostgreSQL mutable truth has no discovery run after the live cycle.")
        listing_state = repository.listing_current_state(representative_listing_id)
        if listing_state is None:
            raise VerificationError(
                f"PostgreSQL mutable truth has no listing_current_state row for listing {representative_listing_id}."
            )
        controller = repository.runtime_controller_state()
        if controller is None:
            raise VerificationError("PostgreSQL mutable truth has no runtime controller state after the live cycle.")
        latest_cycle_id = controller.get("latest_cycle_id")
        if not latest_cycle_id:
            raise VerificationError("Runtime controller state does not expose a latest_cycle_id.")
        runtime_cycle = repository.runtime_cycle(str(latest_cycle_id))
        if runtime_cycle is None:
            raise VerificationError(f"Runtime cycle {latest_cycle_id} was not found in PostgreSQL mutable truth.")
    finally:
        repository.close()

    platform_audit = _validate_platform_audit(db_path=db_path, config=config)
    feature_marts = _validate_feature_marts(
        config=config,
        latest_discovery_run_id=_optional_str(discovery_run.get("run_id")),
        representative_listing_id=representative_listing_id,
    )
    route_parity = verify_clickhouse_routes(
        db_path=db_path,
        listing_id=representative_listing_id,
        timeout=timeout,
        host=host,
        port=0,
        clickhouse_database=config.clickhouse.database,
    )

    object_store = S3ObjectStore.from_config(config)
    try:
        raw_event_keys = _non_marker_keys(object_store, config.storage.raw_events)
        manifest_keys = _non_marker_keys(object_store, config.storage.manifests)
        parquet_keys = _non_marker_keys(object_store, config.storage.parquet)
    finally:
        close = getattr(object_store.client, "close", None)
        if callable(close):
            close()

    for label, keys in (("raw_events", raw_event_keys), ("manifests", manifest_keys), ("parquet", parquet_keys)):
        if not keys:
            raise VerificationError(f"Object storage prefix {label} has no non-marker objects.")

    server = None
    resolved_base_url = base_url.rstrip("/") if base_url else None
    if resolved_base_url is None:
        server = start_dashboard_server(
            db_path=db_path,
            host=host,
            port=port,
            enable_polyglot_reads=True,
        )
        resolved_base_url = f"http://{server.host}:{server.port}"

    try:
        serving_checks = verify_vps_serving(
            resolved_base_url,
            listing_id=representative_listing_id,
            timeout=timeout,
            expected_cutover_mode=expected_cutover_mode,
        )
        dashboard_payload = _fetch_json(_route_url(resolved_base_url, "/api/dashboard"), timeout=timeout)
        explorer_payload = _fetch_json(_route_url(resolved_base_url, "/api/explorer"), timeout=timeout)
    finally:
        if server is not None:
            server.stop()

    dashboard_source = ((dashboard_payload.get("request") or {}).get("primary_payload_source"))
    if dashboard_source != "clickhouse.overview_snapshot":
        raise VerificationError(
            f"Dashboard API primary source drifted to {dashboard_source!r} instead of 'clickhouse.overview_snapshot'."
        )

    explorer_total = int(((explorer_payload.get("results") or {}).get("total_listings") or 0))
    explorer_items = list(explorer_payload.get("items") or [])
    if explorer_total < 1 or not explorer_items:
        raise VerificationError("Explorer API did not return at least one tracked listing under cutover.")

    return {
        "cutover": cutover.as_dict(),
        "doctor": doctor_snapshot.as_dict(),
        "clickhouse_ingest": {
            "reports": ingest_reports,
            "status": ingest_status.as_dict(),
        },
        "platform_audit": {
            "overall_status": platform_audit.get("overall_status"),
            "summary": platform_audit.get("summary"),
            "paths": platform_audit.get("paths"),
        },
        "postgres_truth": {
            "representative_listing_id": representative_listing_id,
            "latest_discovery_run_id": discovery_run.get("run_id"),
            "latest_discovery_run_status": discovery_run.get("status"),
            "listing_current_state": {
                "listing_id": listing_state.get("listing_id"),
                "state_code": listing_state.get("state_code"),
                "latest_probe_outcome": listing_state.get("latest_probe_outcome"),
                "latest_primary_scan_run_id": listing_state.get("latest_primary_scan_run_id"),
            },
            "runtime_controller": {
                "status": controller.get("status"),
                "phase": controller.get("phase"),
                "mode": controller.get("mode"),
                "latest_cycle_id": controller.get("latest_cycle_id"),
            },
            "latest_runtime_cycle": {
                "cycle_id": runtime_cycle.get("cycle_id"),
                "status": runtime_cycle.get("status"),
                "phase": runtime_cycle.get("phase"),
                "discovery_run_id": runtime_cycle.get("discovery_run_id"),
                "state_probed_count": runtime_cycle.get("state_probed_count"),
            },
        },
        "feature_marts": feature_marts,
        "clickhouse_route_parity": route_parity,
        "object_storage": {
            "bucket": config.object_storage.bucket,
            "non_marker_counts": {
                "raw_events": len(raw_event_keys),
                "manifests": len(manifest_keys),
                "parquet": len(parquet_keys),
            },
            "sample_keys": {
                "raw_events": raw_event_keys[:3],
                "manifests": manifest_keys[:3],
                "parquet": parquet_keys[:3],
            },
        },
        "serving": {
            "base_url": resolved_base_url,
            "checks": [asdict(check) for check in serving_checks],
        },
        "dashboard": {
            "primary_payload_source": dashboard_source,
        },
        "explorer": {
            "total_listings": explorer_total,
            "returned_items": len(explorer_items),
            "sample_listing_ids": [item.get("listing_id") for item in explorer_items[:3]],
        },
    }


def _print_human_summary(proof: dict[str, Any]) -> None:
    print("Live cutover smoke proof passed:")
    print(f"- cutover mode: {proof['cutover']['mode']}")
    print(
        "- doctor: postgres={postgres} clickhouse={clickhouse} object-storage={object_storage}".format(
            postgres="ok" if proof["doctor"]["postgres_ok"] else "fail",
            clickhouse="ok" if proof["doctor"]["clickhouse_ok"] else "fail",
            object_storage="ok" if proof["doctor"]["object_storage_ok"] else "fail",
        )
    )
    print(f"- clickhouse ingest: {proof['clickhouse_ingest']['status']['status']}")
    audit_summary = dict(proof["platform_audit"].get("summary") or {})
    print(
        "- platform audit: reconcile={reconcile} current-state={current_state} analytical={analytical} lifecycle={lifecycle} backfill={backfill}".format(
            reconcile=audit_summary.get("reconciliation_status") or "unknown",
            current_state=audit_summary.get("current_state_status") or "unknown",
            analytical=audit_summary.get("analytical_status") or "unknown",
            lifecycle=audit_summary.get("lifecycle_status") or "unknown",
            backfill=audit_summary.get("backfill_status") or "unknown",
        )
    )
    print(
        f"- postgres truth: discovery={proof['postgres_truth']['latest_discovery_run_id']} · "
        f"listing={proof['postgres_truth']['representative_listing_id']} · "
        f"cycle={proof['postgres_truth']['latest_runtime_cycle']['cycle_id']}"
    )
    print(
        "- feature marts: listing-day={listing_day} price-change={price_change} state-transition={state_transition} evidence-packs={packs}".format(
            listing_day=proof["feature_marts"]["listing_day_row_count"],
            price_change=proof["feature_marts"]["price_change_row_count"],
            state_transition=proof["feature_marts"]["state_transition_row_count"],
            packs=proof["feature_marts"]["evidence_pack_row_count"],
        )
    )
    drill_down = dict(proof["feature_marts"].get("evidence_drill_down") or {})
    print(
        f"  - evidence drill-down listing={drill_down.get('listing_id')} · manifests={', '.join(drill_down.get('manifest_ids') or []) or 'n/a'}"
    )
    for command in list(drill_down.get("inspect_examples") or [])[:2]:
        print(f"    - inspect: {command}")
    print(
        "- clickhouse route parity: repository={repository_source} clickhouse={clickhouse_source} parity={parity}".format(
            repository_source=proof["clickhouse_route_parity"]["repository"]["dashboard_source"],
            clickhouse_source=proof["clickhouse_route_parity"]["clickhouse"]["dashboard_source"],
            parity=", ".join(
                f"{label}={status}"
                for label, status in dict(proof["clickhouse_route_parity"].get("parity") or {}).items()
            ),
        )
    )
    print(
        "- object storage: raw_events={raw_events} manifests={manifests} parquet={parquet}".format(
            **proof["object_storage"]["non_marker_counts"]
        )
    )
    print(f"- dashboard source: {proof['dashboard']['primary_payload_source']}")
    print(f"- explorer listings: {proof['explorer']['total_listings']}")
    for check in proof["serving"]["checks"]:
        print(f"  - {check['label']}: HTTP {check['status']} · {check['details']} · {check['url']}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _get_clickhouse_client(config, *, database: str):
    import clickhouse_connect

    parts = urlsplit(config.clickhouse.url)
    return clickhouse_connect.get_client(
        host=parts.hostname or "127.0.0.1",
        port=parts.port or (8443 if parts.scheme == "https" else 8123),
        username=config.clickhouse.username,
        password=config.clickhouse.password,
        database=database,
        secure=parts.scheme == "https",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the live cutover smoke proof against PostgreSQL + ClickHouse + object storage and the served product routes."
    )
    parser.add_argument("--db-path", help="SQLite database path used for the collector cycle and local dashboard verification.")
    parser.add_argument("--listing-id", type=int, help="Representative listing ID to verify. Defaults to the latest PostgreSQL current-state row.")
    parser.add_argument("--base-url", help="Existing served product base URL. If omitted, the script starts a temporary local dashboard server.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds per request.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for the temporary local dashboard server.")
    parser.add_argument("--port", type=int, default=0, help="Bind port for the temporary local dashboard server. Use 0 for an ephemeral port.")
    parser.add_argument(
        "--expected-cutover-mode",
        default="polyglot-cutover",
        help="Cutover mode that the stack and served surfaces must report.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the full proof as JSON.")
    args = parser.parse_args()

    if args.base_url is None and not args.db_path:
        print("FAIL: --db-path is required when --base-url is omitted.", file=sys.stderr)
        return 1

    try:
        proof = verify_cutover_stack(
            db_path=Path(args.db_path) if args.db_path else Path("data/vinted-radar.db"),
            listing_id=args.listing_id,
            base_url=args.base_url,
            timeout=args.timeout,
            host=args.host,
            port=args.port,
            expected_cutover_mode=args.expected_cutover_mode,
        )
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human_summary(proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
