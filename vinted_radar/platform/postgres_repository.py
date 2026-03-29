from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import json
from typing import Any

from vinted_radar.domain.events import canonical_json
from vinted_radar.repository import FULL_SIGNAL_COMPLETENESS, HIGH_SIGNAL_COMPLETENESS
from vinted_radar.state_machine import evaluate_listing_state

POSTGRES_CURRENT_STATE_SINK = "postgres-current-state"
POSTGRES_CURRENT_STATE_CONSUMER = "postgres-current-state-projector"
_RUNTIME_CONTROLLER_SINGLETON_ID = 1


class PostgresMutableTruthRepository:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    # ------------------------------------------------------------------
    # Discovery control-plane projection
    # ------------------------------------------------------------------
    def project_discovery_run_started(
        self,
        *,
        run_id: str,
        started_at: str,
        root_scope: str,
        page_limit: int,
        max_leaf_categories: int | None,
        request_delay_seconds: float,
        event_id: str,
    ) -> None:
        payload = {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": None,
            "status": "running",
            "root_scope": root_scope,
            "page_limit": int(page_limit),
            "max_leaf_categories": None if max_leaf_categories is None else int(max_leaf_categories),
            "request_delay_seconds": float(request_delay_seconds),
            "total_seed_catalogs": 0,
            "total_leaf_catalogs": 0,
            "scanned_leaf_catalogs": 0,
            "successful_scans": 0,
            "failed_scans": 0,
            "raw_listing_hits": 0,
            "unique_listing_hits": 0,
            "last_error": None,
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": started_at,
        }
        self._upsert_discovery_run(payload)

    def project_discovery_catalogs_synced(
        self,
        *,
        run_id: str,
        synced_at: str,
        total_seed_catalogs: int,
        total_leaf_catalogs: int,
        catalogs: Sequence[Mapping[str, object]],
        event_id: str,
    ) -> None:
        for row in catalogs:
            catalog_id = int(row["catalog_id"])
            payload = {
                "catalog_id": catalog_id,
                "root_catalog_id": int(row["root_catalog_id"]),
                "root_title": str(row["root_title"]),
                "parent_catalog_id": _optional_int(row.get("parent_catalog_id")),
                "title": str(row["title"]),
                "code": _optional_str(row.get("code")),
                "url": str(row["url"]),
                "path": str(row["path"]),
                "depth": int(row["depth"]),
                "is_leaf": bool(row["is_leaf"]),
                "allow_browsing_subcategories": bool(row["allow_browsing_subcategories"]),
                "order_index": _optional_int(row.get("order_index")),
                "synced_at": synced_at,
                "last_run_id": run_id,
                "last_event_id": event_id,
                "last_manifest_id": None,
                "projected_at": synced_at,
            }
            self._upsert_catalog(payload)

        existing = self.discovery_run(run_id) or {}
        payload = {
            "run_id": run_id,
            "started_at": _coalesce_str(existing.get("started_at"), synced_at),
            "finished_at": existing.get("finished_at"),
            "status": _coalesce_str(existing.get("status"), "running"),
            "root_scope": _coalesce_str(existing.get("root_scope"), "both"),
            "page_limit": int(existing.get("page_limit") or 1),
            "max_leaf_categories": _optional_int(existing.get("max_leaf_categories")),
            "request_delay_seconds": float(existing.get("request_delay_seconds") or 0.0),
            "total_seed_catalogs": int(total_seed_catalogs),
            "total_leaf_catalogs": int(total_leaf_catalogs),
            "scanned_leaf_catalogs": int(existing.get("scanned_leaf_catalogs") or 0),
            "successful_scans": int(existing.get("successful_scans") or 0),
            "failed_scans": int(existing.get("failed_scans") or 0),
            "raw_listing_hits": int(existing.get("raw_listing_hits") or 0),
            "unique_listing_hits": int(existing.get("unique_listing_hits") or 0),
            "last_error": _optional_str(existing.get("last_error")),
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": synced_at,
        }
        self._upsert_discovery_run(payload)

    def project_discovery_catalog_scan_completed(
        self,
        *,
        run_id: str,
        catalog: Mapping[str, object],
        completed_at: str,
        successful_pages: int,
        failed_pages: int,
        raw_listing_hits: int,
        unique_listing_hits: int,
        listing_rows: Sequence[Mapping[str, object]],
        event_id: str,
    ) -> None:
        catalog_id = int(catalog["catalog_id"])
        root_catalog_id = int(catalog["root_catalog_id"])
        seen_listing_ids: set[int] = set()

        for raw_row in listing_rows:
            row = dict(raw_row)
            listing_id = int(row["listing_id"])
            seen_listing_ids.add(listing_id)
            source_event_id = _optional_str(row.get("source_event_id")) or event_id
            source_manifest_id = _optional_str(row.get("source_manifest_id"))
            observed_at = str(row["observed_at"])
            sighting_count = max(int(row.get("sighting_count") or 1), 1)

            merged_identity = self._merge_listing_identity(
                listing_id=listing_id,
                run_id=run_id,
                observed_at=observed_at,
                row=row,
                source_event_id=source_event_id,
                source_manifest_id=source_manifest_id,
            )
            self._upsert_listing_identity(merged_identity)

            merged_presence = self._merge_listing_presence_summary(
                listing_id=listing_id,
                run_id=run_id,
                observed_at=observed_at,
                sighting_count=sighting_count,
                identity=merged_identity,
                source_event_id=source_event_id,
                source_manifest_id=source_manifest_id,
            )
            self._upsert_listing_presence_summary(merged_presence)

        catalog_row = self.catalog(catalog_id) or {}
        self._upsert_catalog(
            {
                "catalog_id": catalog_id,
                "root_catalog_id": root_catalog_id,
                "root_title": _coalesce_str(catalog.get("root_title"), catalog_row.get("root_title"), "Unknown"),
                "parent_catalog_id": _optional_int(_coalesce(catalog.get("parent_catalog_id"), catalog_row.get("parent_catalog_id"))),
                "title": _coalesce_str(catalog.get("title"), catalog_row.get("title"), str(catalog_id)),
                "code": _optional_str(_coalesce(catalog.get("code"), catalog_row.get("code"))),
                "url": _coalesce_str(catalog.get("url"), catalog_row.get("url"), ""),
                "path": _coalesce_str(catalog.get("path"), catalog_row.get("path"), ""),
                "depth": int(_coalesce(catalog.get("depth"), catalog_row.get("depth"), 0)),
                "is_leaf": bool(_coalesce(catalog.get("is_leaf"), catalog_row.get("is_leaf"), True)),
                "allow_browsing_subcategories": bool(
                    _coalesce(catalog.get("allow_browsing_subcategories"), catalog_row.get("allow_browsing_subcategories"), True)
                ),
                "order_index": _optional_int(_coalesce(catalog.get("order_index"), catalog_row.get("order_index"))),
                "synced_at": _coalesce_str(catalog_row.get("synced_at"), completed_at),
                "last_run_id": run_id,
                "last_event_id": event_id,
                "last_manifest_id": None,
                "projected_at": completed_at,
            }
        )

        affected_listing_ids = set(self.listing_ids_for_catalog(catalog_id)) | seen_listing_ids
        if successful_pages > 0:
            for listing_id in affected_listing_ids:
                current = self.listing_current_state(listing_id) or self._default_listing_current_state(listing_id)
                current.update(
                    {
                        "listing_id": listing_id,
                        "latest_primary_scan_run_id": run_id,
                        "latest_primary_scan_at": completed_at,
                        "seen_in_latest_primary_scan": listing_id in seen_listing_ids,
                        "last_event_id": event_id,
                        "projected_at": completed_at,
                    }
                )
                if listing_id in seen_listing_ids:
                    current["follow_up_miss_count"] = 0
                    current["latest_follow_up_miss_at"] = None
                else:
                    current["follow_up_miss_count"] = int(current.get("follow_up_miss_count") or 0) + 1
                    current["latest_follow_up_miss_at"] = completed_at
                self._upsert_listing_current_state_row(current)
                self._refresh_projected_listing(listing_id, now=completed_at, source_event_id=event_id, source_manifest_id=None)

        existing = self.discovery_run(run_id) or {}
        payload = {
            "run_id": run_id,
            "started_at": _coalesce_str(existing.get("started_at"), completed_at),
            "finished_at": existing.get("finished_at"),
            "status": _coalesce_str(existing.get("status"), "running"),
            "root_scope": _coalesce_str(existing.get("root_scope"), "both"),
            "page_limit": int(existing.get("page_limit") or 1),
            "max_leaf_categories": _optional_int(existing.get("max_leaf_categories")),
            "request_delay_seconds": float(existing.get("request_delay_seconds") or 0.0),
            "total_seed_catalogs": int(existing.get("total_seed_catalogs") or 0),
            "total_leaf_catalogs": int(existing.get("total_leaf_catalogs") or 0),
            "scanned_leaf_catalogs": int(existing.get("scanned_leaf_catalogs") or 0),
            "successful_scans": int(existing.get("successful_scans") or 0),
            "failed_scans": int(existing.get("failed_scans") or 0),
            "raw_listing_hits": int(existing.get("raw_listing_hits") or 0),
            "unique_listing_hits": int(existing.get("unique_listing_hits") or 0),
            "last_error": _optional_str(existing.get("last_error")),
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": completed_at,
        }
        self._upsert_discovery_run(payload)

    def project_discovery_run_completed(
        self,
        *,
        run_id: str,
        finished_at: str,
        status: str,
        scanned_leaf_catalogs: int,
        successful_scans: int,
        failed_scans: int,
        raw_listing_hits: int,
        unique_listing_hits: int,
        last_error: str | None,
        event_id: str,
    ) -> None:
        existing = self.discovery_run(run_id) or {}
        payload = {
            "run_id": run_id,
            "started_at": _coalesce_str(existing.get("started_at"), finished_at),
            "finished_at": finished_at,
            "status": status,
            "root_scope": _coalesce_str(existing.get("root_scope"), "both"),
            "page_limit": int(existing.get("page_limit") or 1),
            "max_leaf_categories": _optional_int(existing.get("max_leaf_categories")),
            "request_delay_seconds": float(existing.get("request_delay_seconds") or 0.0),
            "total_seed_catalogs": int(existing.get("total_seed_catalogs") or 0),
            "total_leaf_catalogs": int(existing.get("total_leaf_catalogs") or 0),
            "scanned_leaf_catalogs": int(scanned_leaf_catalogs),
            "successful_scans": int(successful_scans),
            "failed_scans": int(failed_scans),
            "raw_listing_hits": int(raw_listing_hits),
            "unique_listing_hits": int(unique_listing_hits),
            "last_error": last_error,
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": finished_at,
        }
        self._upsert_discovery_run(payload)

    # ------------------------------------------------------------------
    # Runtime/control-plane projection
    # ------------------------------------------------------------------
    def project_runtime_cycle_snapshot(self, *, cycle: Mapping[str, object], event_id: str) -> None:
        payload = {
            "cycle_id": str(cycle["cycle_id"]),
            "started_at": str(cycle["started_at"]),
            "finished_at": _optional_str(cycle.get("finished_at")),
            "mode": str(cycle["mode"]),
            "status": str(cycle["status"]),
            "phase": str(cycle["phase"]),
            "interval_seconds": _optional_float(cycle.get("interval_seconds")),
            "state_probe_limit": int(cycle.get("state_probe_limit") or 0),
            "discovery_run_id": _optional_str(cycle.get("discovery_run_id")),
            "state_probed_count": int(cycle.get("state_probed_count") or 0),
            "tracked_listings": int(cycle.get("tracked_listings") or 0),
            "first_pass_only": int((cycle.get("freshness_counts") or {}).get("first-pass-only") or cycle.get("first_pass_only") or 0),
            "fresh_followup": int((cycle.get("freshness_counts") or {}).get("fresh-followup") or cycle.get("fresh_followup") or 0),
            "aging_followup": int((cycle.get("freshness_counts") or {}).get("aging-followup") or cycle.get("aging_followup") or 0),
            "stale_followup": int((cycle.get("freshness_counts") or {}).get("stale-followup") or cycle.get("stale_followup") or 0),
            "last_error": _optional_str(cycle.get("last_error")),
            "state_refresh_summary_json": canonical_json(cycle.get("state_refresh_summary") or {}),
            "config_json": canonical_json(cycle.get("config") or {}),
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": _coalesce_str(cycle.get("finished_at"), cycle.get("started_at"), _utc_now()),
        }
        self._upsert_runtime_cycle(payload)

    def project_runtime_controller_snapshot(self, *, controller: Mapping[str, object], event_id: str) -> None:
        payload = {
            "controller_id": _RUNTIME_CONTROLLER_SINGLETON_ID,
            "status": str(controller["status"]),
            "phase": str(controller["phase"]),
            "mode": _optional_str(controller.get("mode")),
            "active_cycle_id": _optional_str(controller.get("active_cycle_id")),
            "latest_cycle_id": _optional_str(controller.get("latest_cycle_id")),
            "interval_seconds": _optional_float(controller.get("interval_seconds")),
            "updated_at": _optional_str(controller.get("updated_at")),
            "paused_at": _optional_str(controller.get("paused_at")),
            "next_resume_at": _optional_str(controller.get("next_resume_at")),
            "last_error": _optional_str(controller.get("last_error")),
            "last_error_at": _optional_str(controller.get("last_error_at")),
            "requested_action": _coalesce_str(controller.get("requested_action"), "none"),
            "requested_at": _optional_str(controller.get("requested_at")),
            "heartbeat_at": _optional_str(controller.get("updated_at")),
            "config_json": canonical_json(controller.get("config") or {}),
            "last_event_id": event_id,
            "last_manifest_id": None,
            "projected_at": _coalesce_str(controller.get("updated_at"), _utc_now()),
        }
        self._upsert_runtime_controller(payload)

    # ------------------------------------------------------------------
    # Current-state projection
    # ------------------------------------------------------------------
    def project_state_refresh_probes(
        self,
        *,
        probe_rows: Sequence[Mapping[str, object]],
        projected_at: str,
        event_id: str,
    ) -> None:
        for raw_row in probe_rows:
            row = dict(raw_row)
            listing_id = int(row["listing_id"])
            source_event_id = _optional_str(row.get("source_event_id")) or event_id
            source_manifest_id = _optional_str(row.get("source_manifest_id"))
            current = self.listing_current_state(listing_id) or self._default_listing_current_state(listing_id)
            current.update(
                {
                    "listing_id": listing_id,
                    "latest_probe_at": str(row["probed_at"]),
                    "latest_probe_response_status": _optional_int(row.get("response_status")),
                    "latest_probe_outcome": _optional_str(row.get("probe_outcome")),
                    "latest_probe_error_message": _optional_str(row.get("error_message")),
                    "last_event_id": source_event_id,
                    "last_manifest_id": source_manifest_id,
                    "projected_at": projected_at,
                }
            )
            self._upsert_listing_current_state_row(current)
            self._refresh_projected_listing(
                listing_id,
                now=str(row["probed_at"]),
                source_event_id=source_event_id,
                source_manifest_id=source_manifest_id,
            )

    # ------------------------------------------------------------------
    # Outbox checkpoint observability
    # ------------------------------------------------------------------
    def update_outbox_checkpoint(
        self,
        *,
        consumer_name: str,
        sink: str,
        last_outbox_id: int | None,
        last_event_id: str | None,
        last_manifest_id: str | None,
        last_claimed_at: str | None,
        last_delivered_at: str | None,
        status: str,
        lag_seconds: float | None,
        last_error: str | None,
        metadata: Mapping[str, object] | None = None,
        updated_at: str | None = None,
    ) -> None:
        payload = {
            "consumer_name": consumer_name,
            "sink": sink,
            "last_outbox_id": last_outbox_id,
            "last_event_id": last_event_id,
            "last_manifest_id": last_manifest_id,
            "last_claimed_at": last_claimed_at,
            "last_delivered_at": last_delivered_at,
            "status": status,
            "lag_seconds": lag_seconds,
            "last_error": last_error,
            "metadata_json": canonical_json(metadata or {}),
            "updated_at": updated_at or _utc_now(),
        }
        try:
            self.connection.execute(
                """
                INSERT INTO platform_outbox_checkpoints (
                    consumer_name,
                    sink,
                    last_outbox_id,
                    last_event_id,
                    last_manifest_id,
                    last_claimed_at,
                    last_delivered_at,
                    status,
                    lag_seconds,
                    last_error,
                    metadata_json,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (consumer_name, sink) DO UPDATE SET
                    last_outbox_id = excluded.last_outbox_id,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    last_claimed_at = excluded.last_claimed_at,
                    last_delivered_at = excluded.last_delivered_at,
                    status = excluded.status,
                    lag_seconds = excluded.lag_seconds,
                    last_error = excluded.last_error,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["consumer_name"],
                    payload["sink"],
                    payload["last_outbox_id"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["last_claimed_at"],
                    payload["last_delivered_at"],
                    payload["status"],
                    payload["lag_seconds"],
                    payload["last_error"],
                    payload["metadata_json"],
                    payload["updated_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    # ------------------------------------------------------------------
    # Read surfaces for tests / future cutover work
    # ------------------------------------------------------------------
    def discovery_run(self, run_id: str) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_discovery_runs WHERE run_id = %s",
                (run_id,),
            )
        )
        return None if row is None else dict(row)

    def latest_discovery_run(self) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_discovery_runs ORDER BY started_at DESC, run_id DESC LIMIT 1"
            )
        )
        return None if row is None else dict(row)

    def catalog(self, catalog_id: int) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_catalogs WHERE catalog_id = %s",
                (catalog_id,),
            )
        )
        return None if row is None else dict(row)

    def listing_identity(self, listing_id: int) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_listing_identity WHERE listing_id = %s",
                (listing_id,),
            )
        )
        return None if row is None else dict(row)

    def listing_presence_summary(self, listing_id: int) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_listing_presence_summary WHERE listing_id = %s",
                (listing_id,),
            )
        )
        return None if row is None else dict(row)

    def listing_current_state(self, listing_id: int) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_listing_current_state WHERE listing_id = %s",
                (listing_id,),
            )
        )
        return None if row is None else dict(row)

    def listing_ids_for_catalog(self, catalog_id: int) -> list[int]:
        rows = _fetchall(
            self.connection.execute(
                "SELECT listing_id FROM platform_listing_identity WHERE primary_catalog_id = %s ORDER BY listing_id ASC",
                (catalog_id,),
            )
        )
        return [int(_row_get(row, "listing_id", 0)) for row in rows]

    def runtime_cycle(self, cycle_id: str) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_runtime_cycles WHERE cycle_id = %s",
                (cycle_id,),
            )
        )
        if row is None:
            return None
        hydrated = dict(row)
        hydrated["config"] = _decode_json_object(hydrated.pop("config_json", "{}"))
        hydrated["state_refresh_summary"] = _decode_json_object(hydrated.pop("state_refresh_summary_json", "{}"))
        hydrated["freshness_counts"] = {
            "first-pass-only": int(hydrated.get("first_pass_only") or 0),
            "fresh-followup": int(hydrated.get("fresh_followup") or 0),
            "aging-followup": int(hydrated.get("aging_followup") or 0),
            "stale-followup": int(hydrated.get("stale_followup") or 0),
        }
        return hydrated

    def runtime_controller_state(self, *, now: str | None = None) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_runtime_controller_state WHERE controller_id = %s",
                (_RUNTIME_CONTROLLER_SINGLETON_ID,),
            )
        )
        if row is None:
            return None
        hydrated = dict(row)
        hydrated["config"] = _decode_json_object(hydrated.pop("config_json", "{}"))
        now_dt = _parse_timestamp(now or _utc_now())
        updated_at = _optional_str(hydrated.get("updated_at"))
        paused_at = _optional_str(hydrated.get("paused_at"))
        next_resume_at = _optional_str(hydrated.get("next_resume_at"))
        age_seconds = None if updated_at is None else max((now_dt - _parse_timestamp(updated_at)).total_seconds(), 0.0)
        elapsed_pause_seconds = None if paused_at is None else max((now_dt - _parse_timestamp(paused_at)).total_seconds(), 0.0)
        next_resume_in_seconds = None if next_resume_at is None else max((_parse_timestamp(next_resume_at) - now_dt).total_seconds(), 0.0)
        stale_after_seconds = _runtime_heartbeat_stale_after_seconds(
            status=_optional_str(hydrated.get("status")),
            interval_seconds=hydrated.get("interval_seconds"),
        )
        hydrated["elapsed_pause_seconds"] = elapsed_pause_seconds
        hydrated["next_resume_in_seconds"] = next_resume_in_seconds
        hydrated["heartbeat"] = {
            "updated_at": updated_at,
            "age_seconds": age_seconds,
            "stale_after_seconds": stale_after_seconds,
            "is_stale": age_seconds is not None and age_seconds > stale_after_seconds,
        }
        return hydrated

    def outbox_checkpoint(self, *, consumer_name: str, sink: str) -> dict[str, object] | None:
        row = _fetchone(
            self.connection.execute(
                "SELECT * FROM platform_outbox_checkpoints WHERE consumer_name = %s AND sink = %s",
                (consumer_name, sink),
            )
        )
        if row is None:
            return None
        hydrated = dict(row)
        hydrated["metadata"] = _decode_json_object(hydrated.pop("metadata_json", "{}"))
        return hydrated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _merge_listing_identity(
        self,
        *,
        listing_id: int,
        run_id: str,
        observed_at: str,
        row: Mapping[str, object],
        source_event_id: str,
        source_manifest_id: str | None,
    ) -> dict[str, object]:
        existing = self.listing_identity(listing_id) or {}
        first_seen_at = _coalesce_str(existing.get("first_seen_at"), observed_at)
        first_seen_run_id = _coalesce_str(existing.get("first_seen_run_id"), run_id)
        if _parse_timestamp(observed_at) < _parse_timestamp(first_seen_at):
            first_seen_at = observed_at
            first_seen_run_id = run_id

        last_seen_at = _coalesce_str(existing.get("last_seen_at"), observed_at)
        last_seen_run_id = _coalesce_str(existing.get("last_seen_run_id"), run_id)
        if _parse_timestamp(observed_at) >= _parse_timestamp(last_seen_at):
            last_seen_at = observed_at
            last_seen_run_id = run_id

        return {
            "listing_id": listing_id,
            "canonical_url": _coalesce_str(row.get("canonical_url"), existing.get("canonical_url"), _coalesce_str(row.get("source_url"), "")),
            "source_url": _coalesce_str(row.get("source_url"), existing.get("source_url"), ""),
            "title": _optional_str(_coalesce(row.get("title"), existing.get("title"))),
            "brand": _optional_str(_coalesce(row.get("brand"), existing.get("brand"))),
            "size_label": _optional_str(_coalesce(row.get("size_label"), existing.get("size_label"))),
            "condition_label": _optional_str(_coalesce(row.get("condition_label"), existing.get("condition_label"))),
            "price_amount_cents": _optional_int(_coalesce(row.get("price_amount_cents"), existing.get("price_amount_cents"))),
            "price_currency": _optional_str(_coalesce(row.get("price_currency"), existing.get("price_currency"))),
            "total_price_amount_cents": _optional_int(_coalesce(row.get("total_price_amount_cents"), existing.get("total_price_amount_cents"))),
            "total_price_currency": _optional_str(_coalesce(row.get("total_price_currency"), existing.get("total_price_currency"))),
            "image_url": _optional_str(_coalesce(row.get("image_url"), existing.get("image_url"))),
            "favourite_count": _optional_int(_coalesce(row.get("favourite_count"), existing.get("favourite_count"))),
            "view_count": _optional_int(_coalesce(row.get("view_count"), existing.get("view_count"))),
            "user_id": _optional_int(_coalesce(row.get("user_id"), existing.get("user_id"))),
            "user_login": _optional_str(_coalesce(row.get("user_login"), existing.get("user_login"))),
            "user_profile_url": _optional_str(_coalesce(row.get("user_profile_url"), existing.get("user_profile_url"))),
            "created_at_ts": _optional_int(_coalesce(row.get("created_at_ts"), existing.get("created_at_ts"))),
            "primary_catalog_id": _optional_int(_coalesce(row.get("catalog_id"), existing.get("primary_catalog_id"))),
            "primary_root_catalog_id": _optional_int(_coalesce(row.get("root_catalog_id"), existing.get("primary_root_catalog_id"))),
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "first_seen_run_id": first_seen_run_id,
            "last_seen_run_id": last_seen_run_id,
            "last_event_id": source_event_id,
            "last_manifest_id": source_manifest_id,
            "projected_at": observed_at,
        }

    def _merge_listing_presence_summary(
        self,
        *,
        listing_id: int,
        run_id: str,
        observed_at: str,
        sighting_count: int,
        identity: Mapping[str, object],
        source_event_id: str,
        source_manifest_id: str | None,
    ) -> dict[str, object]:
        existing = self.listing_presence_summary(listing_id)
        if existing is None:
            observation_count = 1
            total_sightings = sighting_count
            first_seen_at = observed_at
            last_seen_at = observed_at
            average_revisit_hours = None
            last_observed_run_id = run_id
        elif _coalesce_str(existing.get("last_observed_run_id"), "") == run_id:
            observation_count = int(existing.get("observation_count") or 0)
            total_sightings = int(existing.get("total_sightings") or 0) + sighting_count
            first_seen_at = _coalesce_str(existing.get("first_seen_at"), observed_at)
            last_seen_at = _coalesce_str(existing.get("last_seen_at"), observed_at)
            if _parse_timestamp(observed_at) > _parse_timestamp(last_seen_at):
                last_seen_at = observed_at
            average_revisit_hours = _optional_float(existing.get("average_revisit_hours"))
            last_observed_run_id = run_id
        else:
            previous_observation_count = int(existing.get("observation_count") or 0)
            previous_average = _optional_float(existing.get("average_revisit_hours"))
            previous_last_seen_at = _coalesce_str(existing.get("last_seen_at"), observed_at)
            if _parse_timestamp(observed_at) <= _parse_timestamp(previous_last_seen_at):
                return dict(existing)
            observation_count = previous_observation_count + 1
            total_sightings = int(existing.get("total_sightings") or 0) + sighting_count
            first_seen_at = _coalesce_str(existing.get("first_seen_at"), observed_at)
            last_seen_at = observed_at
            interval_hours = max((_parse_timestamp(observed_at) - _parse_timestamp(previous_last_seen_at)).total_seconds() / 3600.0, 0.0)
            if previous_observation_count <= 1 or previous_average is None:
                average_revisit_hours = round(interval_hours, 2)
            else:
                interval_count = previous_observation_count - 1
                average_revisit_hours = round(((previous_average * interval_count) + interval_hours) / (interval_count + 1), 2)
            last_observed_run_id = run_id

        signal_completeness = _signal_completeness(identity)
        price_band_code, price_band_label, price_band_sort_order = _price_band(identity.get("price_amount_cents"))
        age_hours = _age_hours(last_seen_at, observed_at)
        return {
            "listing_id": listing_id,
            "observation_count": observation_count,
            "total_sightings": total_sightings,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "average_revisit_hours": average_revisit_hours,
            "last_observed_run_id": last_observed_run_id,
            "freshness_bucket": _freshness_bucket(observation_count, age_hours),
            "signal_completeness": signal_completeness,
            "partial_signal": signal_completeness < FULL_SIGNAL_COMPLETENESS,
            "thin_signal": signal_completeness < HIGH_SIGNAL_COMPLETENESS,
            "has_estimated_publication": identity.get("created_at_ts") is not None,
            "price_band_code": price_band_code,
            "price_band_label": price_band_label,
            "price_band_sort_order": price_band_sort_order,
            "last_event_id": source_event_id,
            "last_manifest_id": source_manifest_id,
            "projected_at": observed_at,
        }

    def _refresh_projected_listing(
        self,
        listing_id: int,
        *,
        now: str,
        source_event_id: str,
        source_manifest_id: str | None,
    ) -> None:
        identity = self.listing_identity(listing_id)
        presence = self.listing_presence_summary(listing_id)
        current = self.listing_current_state(listing_id) or self._default_listing_current_state(listing_id)
        if identity is None or presence is None:
            return

        age_hours = round(_age_hours(str(presence["last_seen_at"]), now), 2)
        signal_completeness = _signal_completeness(identity)
        latest_probe = None
        if current.get("latest_probe_at") is not None:
            latest_probe = {
                "probed_at": current.get("latest_probe_at"),
                "response_status": current.get("latest_probe_response_status"),
                "probe_outcome": current.get("latest_probe_outcome"),
                "error_message": current.get("latest_probe_error_message"),
            }
        evidence = {
            "listing_id": listing_id,
            "observation_count": int(presence.get("observation_count") or 0),
            "total_sightings": int(presence.get("total_sightings") or 0),
            "first_seen_at": presence.get("first_seen_at"),
            "last_seen_at": presence.get("last_seen_at"),
            "average_revisit_hours": presence.get("average_revisit_hours"),
            "canonical_url": identity.get("canonical_url"),
            "title": identity.get("title"),
            "brand": identity.get("brand"),
            "size_label": identity.get("size_label"),
            "condition_label": identity.get("condition_label"),
            "price_amount_cents": identity.get("price_amount_cents"),
            "price_currency": identity.get("price_currency"),
            "total_price_amount_cents": identity.get("total_price_amount_cents"),
            "total_price_currency": identity.get("total_price_currency"),
            "image_url": identity.get("image_url"),
            "favourite_count": identity.get("favourite_count"),
            "view_count": identity.get("view_count"),
            "user_id": identity.get("user_id"),
            "user_login": identity.get("user_login"),
            "user_profile_url": identity.get("user_profile_url"),
            "created_at_ts": identity.get("created_at_ts"),
            "primary_catalog_id": identity.get("primary_catalog_id"),
            "primary_root_catalog_id": identity.get("primary_root_catalog_id"),
            "last_observed_run_id": presence.get("last_observed_run_id"),
            "latest_primary_scan_run_id": current.get("latest_primary_scan_run_id"),
            "latest_primary_scan_at": current.get("latest_primary_scan_at"),
            "follow_up_miss_count": int(current.get("follow_up_miss_count") or 0),
            "latest_follow_up_miss_at": current.get("latest_follow_up_miss_at"),
            "seen_in_latest_primary_scan": bool(current.get("seen_in_latest_primary_scan")),
            "latest_probe": latest_probe,
            "last_seen_age_hours": age_hours,
            "signal_completeness": signal_completeness,
            "freshness_bucket": _freshness_bucket(int(presence.get("observation_count") or 0), age_hours),
        }
        evaluation = evaluate_listing_state(evidence, now=now)
        price_band_code, price_band_label, price_band_sort_order = _price_band(identity.get("price_amount_cents"))
        updated_presence = dict(presence)
        updated_presence.update(
            {
                "freshness_bucket": str(evidence["freshness_bucket"]),
                "signal_completeness": signal_completeness,
                "partial_signal": signal_completeness < FULL_SIGNAL_COMPLETENESS,
                "thin_signal": signal_completeness < HIGH_SIGNAL_COMPLETENESS,
                "has_estimated_publication": identity.get("created_at_ts") is not None,
                "price_band_code": price_band_code,
                "price_band_label": price_band_label,
                "price_band_sort_order": price_band_sort_order,
                "last_event_id": source_event_id,
                "last_manifest_id": source_manifest_id,
                "projected_at": now,
            }
        )
        self._upsert_listing_presence_summary(updated_presence)

        current.update(
            {
                "listing_id": listing_id,
                "state_code": str(evaluation["state_code"]),
                "state_label": _state_label(str(evaluation["state_code"])),
                "basis_kind": str(evaluation["basis_kind"]),
                "confidence_label": str(evaluation["confidence_label"]),
                "confidence_score": float(evaluation["confidence_score"]),
                "sold_like": str(evaluation["state_code"]) in {"sold_observed", "sold_probable"},
                "last_seen_age_hours": age_hours,
                "state_explanation_json": canonical_json(evaluation.get("state_explanation") or {}),
                "last_event_id": source_event_id,
                "last_manifest_id": source_manifest_id,
                "projected_at": now,
            }
        )
        self._upsert_listing_current_state_row(current)

    def _default_listing_current_state(self, listing_id: int) -> dict[str, object]:
        return {
            "listing_id": listing_id,
            "state_code": "unknown",
            "state_label": _state_label("unknown"),
            "basis_kind": "unknown",
            "confidence_label": "low",
            "confidence_score": 0.0,
            "sold_like": False,
            "seen_in_latest_primary_scan": False,
            "latest_primary_scan_run_id": None,
            "latest_primary_scan_at": None,
            "follow_up_miss_count": 0,
            "latest_follow_up_miss_at": None,
            "latest_probe_at": None,
            "latest_probe_response_status": None,
            "latest_probe_outcome": None,
            "latest_probe_error_message": None,
            "last_seen_age_hours": 0.0,
            "state_explanation_json": canonical_json({}),
            "last_event_id": None,
            "last_manifest_id": None,
            "projected_at": _utc_now(),
        }

    # ------------------------------------------------------------------
    # Low-level SQL upserts
    # ------------------------------------------------------------------
    def _upsert_discovery_run(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_discovery_runs (
                    run_id,
                    started_at,
                    finished_at,
                    status,
                    root_scope,
                    page_limit,
                    max_leaf_categories,
                    request_delay_seconds,
                    total_seed_catalogs,
                    total_leaf_catalogs,
                    scanned_leaf_catalogs,
                    successful_scans,
                    failed_scans,
                    raw_listing_hits,
                    unique_listing_hits,
                    last_error,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    status = excluded.status,
                    root_scope = excluded.root_scope,
                    page_limit = excluded.page_limit,
                    max_leaf_categories = excluded.max_leaf_categories,
                    request_delay_seconds = excluded.request_delay_seconds,
                    total_seed_catalogs = excluded.total_seed_catalogs,
                    total_leaf_catalogs = excluded.total_leaf_catalogs,
                    scanned_leaf_catalogs = excluded.scanned_leaf_catalogs,
                    successful_scans = excluded.successful_scans,
                    failed_scans = excluded.failed_scans,
                    raw_listing_hits = excluded.raw_listing_hits,
                    unique_listing_hits = excluded.unique_listing_hits,
                    last_error = excluded.last_error,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["run_id"],
                    payload["started_at"],
                    payload["finished_at"],
                    payload["status"],
                    payload["root_scope"],
                    payload["page_limit"],
                    payload["max_leaf_categories"],
                    payload["request_delay_seconds"],
                    payload["total_seed_catalogs"],
                    payload["total_leaf_catalogs"],
                    payload["scanned_leaf_catalogs"],
                    payload["successful_scans"],
                    payload["failed_scans"],
                    payload["raw_listing_hits"],
                    payload["unique_listing_hits"],
                    payload["last_error"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_catalog(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_catalogs (
                    catalog_id,
                    root_catalog_id,
                    root_title,
                    parent_catalog_id,
                    title,
                    code,
                    url,
                    path,
                    depth,
                    is_leaf,
                    allow_browsing_subcategories,
                    order_index,
                    synced_at,
                    last_run_id,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (catalog_id) DO UPDATE SET
                    root_catalog_id = excluded.root_catalog_id,
                    root_title = excluded.root_title,
                    parent_catalog_id = excluded.parent_catalog_id,
                    title = excluded.title,
                    code = excluded.code,
                    url = excluded.url,
                    path = excluded.path,
                    depth = excluded.depth,
                    is_leaf = excluded.is_leaf,
                    allow_browsing_subcategories = excluded.allow_browsing_subcategories,
                    order_index = excluded.order_index,
                    synced_at = excluded.synced_at,
                    last_run_id = excluded.last_run_id,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["catalog_id"],
                    payload["root_catalog_id"],
                    payload["root_title"],
                    payload["parent_catalog_id"],
                    payload["title"],
                    payload["code"],
                    payload["url"],
                    payload["path"],
                    payload["depth"],
                    payload["is_leaf"],
                    payload["allow_browsing_subcategories"],
                    payload["order_index"],
                    payload["synced_at"],
                    payload["last_run_id"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_listing_identity(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_listing_identity (
                    listing_id,
                    canonical_url,
                    source_url,
                    title,
                    brand,
                    size_label,
                    condition_label,
                    price_amount_cents,
                    price_currency,
                    total_price_amount_cents,
                    total_price_currency,
                    image_url,
                    favourite_count,
                    view_count,
                    user_id,
                    user_login,
                    user_profile_url,
                    created_at_ts,
                    primary_catalog_id,
                    primary_root_catalog_id,
                    first_seen_at,
                    last_seen_at,
                    first_seen_run_id,
                    last_seen_run_id,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (listing_id) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    source_url = excluded.source_url,
                    title = excluded.title,
                    brand = excluded.brand,
                    size_label = excluded.size_label,
                    condition_label = excluded.condition_label,
                    price_amount_cents = excluded.price_amount_cents,
                    price_currency = excluded.price_currency,
                    total_price_amount_cents = excluded.total_price_amount_cents,
                    total_price_currency = excluded.total_price_currency,
                    image_url = excluded.image_url,
                    favourite_count = excluded.favourite_count,
                    view_count = excluded.view_count,
                    user_id = excluded.user_id,
                    user_login = excluded.user_login,
                    user_profile_url = excluded.user_profile_url,
                    created_at_ts = excluded.created_at_ts,
                    primary_catalog_id = excluded.primary_catalog_id,
                    primary_root_catalog_id = excluded.primary_root_catalog_id,
                    first_seen_at = excluded.first_seen_at,
                    last_seen_at = excluded.last_seen_at,
                    first_seen_run_id = excluded.first_seen_run_id,
                    last_seen_run_id = excluded.last_seen_run_id,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["listing_id"],
                    payload["canonical_url"],
                    payload["source_url"],
                    payload["title"],
                    payload["brand"],
                    payload["size_label"],
                    payload["condition_label"],
                    payload["price_amount_cents"],
                    payload["price_currency"],
                    payload["total_price_amount_cents"],
                    payload["total_price_currency"],
                    payload["image_url"],
                    payload["favourite_count"],
                    payload["view_count"],
                    payload["user_id"],
                    payload["user_login"],
                    payload["user_profile_url"],
                    payload["created_at_ts"],
                    payload["primary_catalog_id"],
                    payload["primary_root_catalog_id"],
                    payload["first_seen_at"],
                    payload["last_seen_at"],
                    payload["first_seen_run_id"],
                    payload["last_seen_run_id"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_listing_presence_summary(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_listing_presence_summary (
                    listing_id,
                    observation_count,
                    total_sightings,
                    first_seen_at,
                    last_seen_at,
                    average_revisit_hours,
                    last_observed_run_id,
                    freshness_bucket,
                    signal_completeness,
                    partial_signal,
                    thin_signal,
                    has_estimated_publication,
                    price_band_code,
                    price_band_label,
                    price_band_sort_order,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (listing_id) DO UPDATE SET
                    observation_count = excluded.observation_count,
                    total_sightings = excluded.total_sightings,
                    first_seen_at = excluded.first_seen_at,
                    last_seen_at = excluded.last_seen_at,
                    average_revisit_hours = excluded.average_revisit_hours,
                    last_observed_run_id = excluded.last_observed_run_id,
                    freshness_bucket = excluded.freshness_bucket,
                    signal_completeness = excluded.signal_completeness,
                    partial_signal = excluded.partial_signal,
                    thin_signal = excluded.thin_signal,
                    has_estimated_publication = excluded.has_estimated_publication,
                    price_band_code = excluded.price_band_code,
                    price_band_label = excluded.price_band_label,
                    price_band_sort_order = excluded.price_band_sort_order,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["listing_id"],
                    payload["observation_count"],
                    payload["total_sightings"],
                    payload["first_seen_at"],
                    payload["last_seen_at"],
                    payload["average_revisit_hours"],
                    payload["last_observed_run_id"],
                    payload["freshness_bucket"],
                    payload["signal_completeness"],
                    payload["partial_signal"],
                    payload["thin_signal"],
                    payload["has_estimated_publication"],
                    payload["price_band_code"],
                    payload["price_band_label"],
                    payload["price_band_sort_order"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_listing_current_state_row(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_listing_current_state (
                    listing_id,
                    state_code,
                    state_label,
                    basis_kind,
                    confidence_label,
                    confidence_score,
                    sold_like,
                    seen_in_latest_primary_scan,
                    latest_primary_scan_run_id,
                    latest_primary_scan_at,
                    follow_up_miss_count,
                    latest_follow_up_miss_at,
                    latest_probe_at,
                    latest_probe_response_status,
                    latest_probe_outcome,
                    latest_probe_error_message,
                    last_seen_age_hours,
                    state_explanation_json,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (listing_id) DO UPDATE SET
                    state_code = excluded.state_code,
                    state_label = excluded.state_label,
                    basis_kind = excluded.basis_kind,
                    confidence_label = excluded.confidence_label,
                    confidence_score = excluded.confidence_score,
                    sold_like = excluded.sold_like,
                    seen_in_latest_primary_scan = excluded.seen_in_latest_primary_scan,
                    latest_primary_scan_run_id = excluded.latest_primary_scan_run_id,
                    latest_primary_scan_at = excluded.latest_primary_scan_at,
                    follow_up_miss_count = excluded.follow_up_miss_count,
                    latest_follow_up_miss_at = excluded.latest_follow_up_miss_at,
                    latest_probe_at = excluded.latest_probe_at,
                    latest_probe_response_status = excluded.latest_probe_response_status,
                    latest_probe_outcome = excluded.latest_probe_outcome,
                    latest_probe_error_message = excluded.latest_probe_error_message,
                    last_seen_age_hours = excluded.last_seen_age_hours,
                    state_explanation_json = excluded.state_explanation_json,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["listing_id"],
                    payload["state_code"],
                    payload["state_label"],
                    payload["basis_kind"],
                    payload["confidence_label"],
                    payload["confidence_score"],
                    payload["sold_like"],
                    payload["seen_in_latest_primary_scan"],
                    payload.get("latest_primary_scan_run_id"),
                    payload.get("latest_primary_scan_at"),
                    payload.get("follow_up_miss_count", 0),
                    payload.get("latest_follow_up_miss_at"),
                    payload.get("latest_probe_at"),
                    payload.get("latest_probe_response_status"),
                    payload.get("latest_probe_outcome"),
                    payload.get("latest_probe_error_message"),
                    payload.get("last_seen_age_hours", 0.0),
                    payload.get("state_explanation_json", canonical_json({})),
                    payload.get("last_event_id"),
                    payload.get("last_manifest_id"),
                    payload.get("projected_at", _utc_now()),
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_runtime_cycle(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_runtime_cycles (
                    cycle_id,
                    started_at,
                    finished_at,
                    mode,
                    status,
                    phase,
                    interval_seconds,
                    state_probe_limit,
                    discovery_run_id,
                    state_probed_count,
                    tracked_listings,
                    first_pass_only,
                    fresh_followup,
                    aging_followup,
                    stale_followup,
                    last_error,
                    state_refresh_summary_json,
                    config_json,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
                ON CONFLICT (cycle_id) DO UPDATE SET
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    mode = excluded.mode,
                    status = excluded.status,
                    phase = excluded.phase,
                    interval_seconds = excluded.interval_seconds,
                    state_probe_limit = excluded.state_probe_limit,
                    discovery_run_id = excluded.discovery_run_id,
                    state_probed_count = excluded.state_probed_count,
                    tracked_listings = excluded.tracked_listings,
                    first_pass_only = excluded.first_pass_only,
                    fresh_followup = excluded.fresh_followup,
                    aging_followup = excluded.aging_followup,
                    stale_followup = excluded.stale_followup,
                    last_error = excluded.last_error,
                    state_refresh_summary_json = excluded.state_refresh_summary_json,
                    config_json = excluded.config_json,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["cycle_id"],
                    payload["started_at"],
                    payload["finished_at"],
                    payload["mode"],
                    payload["status"],
                    payload["phase"],
                    payload["interval_seconds"],
                    payload["state_probe_limit"],
                    payload["discovery_run_id"],
                    payload["state_probed_count"],
                    payload["tracked_listings"],
                    payload["first_pass_only"],
                    payload["fresh_followup"],
                    payload["aging_followup"],
                    payload["stale_followup"],
                    payload["last_error"],
                    payload["state_refresh_summary_json"],
                    payload["config_json"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise

    def _upsert_runtime_controller(self, payload: Mapping[str, object]) -> None:
        try:
            self.connection.execute(
                """
                INSERT INTO platform_runtime_controller_state (
                    controller_id,
                    status,
                    phase,
                    mode,
                    active_cycle_id,
                    latest_cycle_id,
                    interval_seconds,
                    updated_at,
                    paused_at,
                    next_resume_at,
                    last_error,
                    last_error_at,
                    requested_action,
                    requested_at,
                    heartbeat_at,
                    config_json,
                    last_event_id,
                    last_manifest_id,
                    projected_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (controller_id) DO UPDATE SET
                    status = excluded.status,
                    phase = excluded.phase,
                    mode = excluded.mode,
                    active_cycle_id = excluded.active_cycle_id,
                    latest_cycle_id = excluded.latest_cycle_id,
                    interval_seconds = excluded.interval_seconds,
                    updated_at = excluded.updated_at,
                    paused_at = excluded.paused_at,
                    next_resume_at = excluded.next_resume_at,
                    last_error = excluded.last_error,
                    last_error_at = excluded.last_error_at,
                    requested_action = excluded.requested_action,
                    requested_at = excluded.requested_at,
                    heartbeat_at = excluded.heartbeat_at,
                    config_json = excluded.config_json,
                    last_event_id = excluded.last_event_id,
                    last_manifest_id = excluded.last_manifest_id,
                    projected_at = excluded.projected_at
                """,
                (
                    payload["controller_id"],
                    payload["status"],
                    payload["phase"],
                    payload["mode"],
                    payload["active_cycle_id"],
                    payload["latest_cycle_id"],
                    payload["interval_seconds"],
                    payload["updated_at"],
                    payload["paused_at"],
                    payload["next_resume_at"],
                    payload["last_error"],
                    payload["last_error_at"],
                    payload["requested_action"],
                    payload["requested_at"],
                    payload["heartbeat_at"],
                    payload["config_json"],
                    payload["last_event_id"],
                    payload["last_manifest_id"],
                    payload["projected_at"],
                ),
            )
            _commit_quietly(self.connection)
        except Exception:  # noqa: BLE001
            _rollback_quietly(self.connection)
            raise


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _fetchone(result: object) -> object | None:
    fetchone = getattr(result, "fetchone", None)
    return None if not callable(fetchone) else fetchone()



def _fetchall(result: object) -> list[object]:
    fetchall = getattr(result, "fetchall", None)
    if not callable(fetchall):
        return []
    return list(fetchall())



def _commit_quietly(connection: object) -> None:
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()



def _rollback_quietly(connection: object) -> None:
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        rollback()



def _row_get(row: object, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    if isinstance(row, Sequence):
        return row[index]
    raise TypeError(f"Unsupported row type: {type(row).__name__}")



def _decode_json_object(value: object) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}



def _parse_timestamp(value: str) -> datetime:
    candidate = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)



def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()



def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None



def _coalesce(primary: object, fallback: object, default: object | None = None) -> object | None:
    if primary is not None:
        return primary
    if fallback is not None:
        return fallback
    return default



def _coalesce_str(primary: object, fallback: object | None = None, default: str | None = None) -> str:
    for value in (primary, fallback, default):
        candidate = _optional_str(value)
        if candidate is not None:
            return candidate
    return ""



def _signal_completeness(row: Mapping[str, object]) -> int:
    return sum(
        1
        for field in (
            "title",
            "brand",
            "size_label",
            "condition_label",
            "price_amount_cents",
            "total_price_amount_cents",
            "image_url",
        )
        if row.get(field) is not None
    )



def _price_band(price_amount_cents: object) -> tuple[str, str, int]:
    price = _optional_int(price_amount_cents)
    if price is None:
        return "unknown", "Prix indisponible", 4
    if price < 2000:
        return "under_20_eur", "< 20 €", 1
    if price < 4000:
        return "20_to_39_eur", "20–39 €", 2
    return "40_plus_eur", "40 € et plus", 3



def _freshness_bucket(observation_count: int, age_hours: float) -> str:
    if observation_count <= 1:
        return "first-pass-only"
    if age_hours <= 24.0:
        return "fresh-followup"
    if age_hours <= 72.0:
        return "aging-followup"
    return "stale-followup"



def _age_hours(timestamp: str, now: str) -> float:
    return max((_parse_timestamp(now) - _parse_timestamp(timestamp)).total_seconds() / 3600.0, 0.0)



def _state_label(state_code: str) -> str:
    return {
        "active": "Actif",
        "sold_observed": "Vendu observé",
        "sold_probable": "Vendu probable",
        "unavailable_non_conclusive": "Indisponible",
        "deleted": "Supprimée",
        "unknown": "Inconnu",
    }.get(state_code, "Inconnu")



def _runtime_heartbeat_stale_after_seconds(*, status: str | None, interval_seconds: object) -> float:
    if status in {"running", "scheduled"}:
        return 30.0
    if status == "paused":
        return 120.0
    interval = _optional_float(interval_seconds)
    if interval is not None:
        return max(min(interval, 300.0), 60.0)
    return 300.0


__all__ = [
    "POSTGRES_CURRENT_STATE_CONSUMER",
    "POSTGRES_CURRENT_STATE_SINK",
    "PostgresMutableTruthRepository",
]
