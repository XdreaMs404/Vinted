from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
import uuid

from vinted_radar.card_payload import normalize_card_snapshot
from vinted_radar.db import connect_database
from vinted_radar.models import CatalogNode, ListingCard
from vinted_radar.state_machine import (
    ACTIVE_LATEST_SCAN_OBSERVED_CONFIDENCE,
    ACTIVE_PROBE_OBSERVED_CONFIDENCE,
    ACTIVE_RECENT_NO_RESCAN_INFERRED_CONFIDENCE,
    ACTIVE_RECENT_WITHOUT_RESCAN_HOURS,
    DELETED_OBSERVED_CONFIDENCE,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
    SOLD_OBSERVED_CONFIDENCE,
    SOLD_PROBABLE_MULTI_MISS_CONFIDENCE,
    SOLD_PROBABLE_TWO_MISS_CONFIDENCE,
    STALE_HISTORY_UNKNOWN_HOURS,
    STATE_ORDER,
    UNAVAILABLE_OBSERVED_CONFIDENCE,
    UNAVAILABLE_SINGLE_MISS_INFERRED_CONFIDENCE,
    UNKNOWN_INCONCLUSIVE_CONFIDENCE,
    UNKNOWN_STALE_CONFIDENCE,
)

FRESH_FOLLOWUP_HOURS = 24.0
STALE_FOLLOWUP_HOURS = 72.0
FULL_SIGNAL_COMPLETENESS = 7
HIGH_SIGNAL_COMPLETENESS = 5
DEFAULT_OVERVIEW_COMPARISON_LIMIT = 6
DEFAULT_OVERVIEW_SUPPORT_THRESHOLD = 3
_RUNTIME_CONTROLLER_SINGLETON_ID = 1
_UNSET = object()
_SENSITIVE_URL_USERINFO_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@\s]+(?::[^/@\s]*)?@)")


class RadarRepository(AbstractContextManager["RadarRepository"]):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.connection = connect_database(self.db_path)

    def close(self) -> None:
        self.connection.close()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start_run(
        self,
        *,
        root_scope: str,
        page_limit: int,
        max_leaf_categories: int | None,
        request_delay_seconds: float,
    ) -> str:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        started_at = _utc_now()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO discovery_runs (
                    run_id, started_at, status, root_scope, page_limit,
                    max_leaf_categories, request_delay_seconds
                ) VALUES (?, ?, 'running', ?, ?, ?, ?)
                """,
                (run_id, started_at, root_scope, page_limit, max_leaf_categories, request_delay_seconds),
            )
        return run_id

    def update_run_catalog_totals(self, run_id: str, *, total_seed_catalogs: int, total_leaf_catalogs: int) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE discovery_runs SET total_seed_catalogs = ?, total_leaf_catalogs = ? WHERE run_id = ?",
                (total_seed_catalogs, total_leaf_catalogs, run_id),
            )

    def complete_run(
        self,
        run_id: str,
        *,
        status: str,
        scanned_leaf_catalogs: int,
        successful_scans: int,
        failed_scans: int,
        raw_listing_hits: int,
        unique_listing_hits: int,
        last_error: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE discovery_runs
                SET finished_at = ?, status = ?, scanned_leaf_catalogs = ?,
                    successful_scans = ?, failed_scans = ?,
                    raw_listing_hits = ?, unique_listing_hits = ?, last_error = ?
                WHERE run_id = ?
                """,
                (
                    _utc_now(),
                    status,
                    scanned_leaf_catalogs,
                    successful_scans,
                    failed_scans,
                    raw_listing_hits,
                    unique_listing_hits,
                    last_error,
                    run_id,
                ),
            )

    def upsert_catalogs(self, catalogs: Iterable[CatalogNode], *, synced_at: str) -> None:
        payload = [
            (
                catalog.catalog_id,
                catalog.root_catalog_id,
                catalog.root_title,
                catalog.parent_catalog_id,
                catalog.title,
                catalog.code,
                catalog.url,
                catalog.path_text,
                catalog.depth,
                int(catalog.is_leaf),
                int(catalog.allow_browsing_subcategories),
                catalog.order_index,
                synced_at,
            )
            for catalog in catalogs
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO catalogs (
                    catalog_id, root_catalog_id, root_title, parent_catalog_id, title,
                    code, url, path, depth, is_leaf, allow_browsing_subcategories,
                    order_index, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(catalog_id) DO UPDATE SET
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
                    synced_at = excluded.synced_at
                """,
                payload,
            )

    def record_catalog_scan(
        self,
        *,
        run_id: str,
        catalog_id: int,
        page_number: int,
        requested_url: str,
        fetched_at: str,
        response_status: int | None,
        success: bool,
        listing_count: int,
        pagination_total_pages: int | None,
        next_page_url: str | None,
        error_message: str | None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO catalog_scans (
                    run_id, catalog_id, page_number, requested_url, fetched_at, response_status,
                    success, listing_count, pagination_total_pages, next_page_url, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    catalog_id,
                    page_number,
                    requested_url,
                    fetched_at,
                    response_status,
                    int(success),
                    listing_count,
                    pagination_total_pages,
                    next_page_url,
                    error_message,
                ),
            )

    def upsert_listing(
        self,
        listing: ListingCard,
        *,
        discovered_at: str,
        primary_catalog_id: int,
        primary_root_catalog_id: int,
        run_id: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO listings (
                    listing_id, canonical_url, source_url, title, brand, size_label,
                    condition_label, price_amount_cents, price_currency,
                    total_price_amount_cents, total_price_currency, image_url,
                    favourite_count, view_count, user_id, user_login, user_profile_url, created_at_ts,
                    primary_catalog_id, primary_root_catalog_id,
                    first_discovered_at, last_discovered_at, last_seen_run_id,
                    last_card_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    source_url = excluded.source_url,
                    title = COALESCE(excluded.title, listings.title),
                    brand = COALESCE(excluded.brand, listings.brand),
                    size_label = COALESCE(excluded.size_label, listings.size_label),
                    condition_label = COALESCE(excluded.condition_label, listings.condition_label),
                    price_amount_cents = COALESCE(excluded.price_amount_cents, listings.price_amount_cents),
                    price_currency = COALESCE(excluded.price_currency, listings.price_currency),
                    total_price_amount_cents = COALESCE(excluded.total_price_amount_cents, listings.total_price_amount_cents),
                    total_price_currency = COALESCE(excluded.total_price_currency, listings.total_price_currency),
                    image_url = COALESCE(excluded.image_url, listings.image_url),
                    favourite_count = COALESCE(excluded.favourite_count, listings.favourite_count),
                    view_count = COALESCE(excluded.view_count, listings.view_count),
                    user_id = COALESCE(excluded.user_id, listings.user_id),
                    user_login = COALESCE(excluded.user_login, listings.user_login),
                    user_profile_url = COALESCE(excluded.user_profile_url, listings.user_profile_url),
                    created_at_ts = COALESCE(excluded.created_at_ts, listings.created_at_ts),
                    primary_catalog_id = COALESCE(excluded.primary_catalog_id, listings.primary_catalog_id),
                    primary_root_catalog_id = COALESCE(excluded.primary_root_catalog_id, listings.primary_root_catalog_id),
                    last_discovered_at = excluded.last_discovered_at,
                    last_seen_run_id = excluded.last_seen_run_id,
                    last_card_payload_json = excluded.last_card_payload_json
                """,
                (
                    listing.listing_id,
                    listing.canonical_url,
                    listing.source_url,
                    listing.title,
                    listing.brand,
                    listing.size_label,
                    listing.condition_label,
                    listing.price_amount_cents,
                    listing.price_currency,
                    listing.total_price_amount_cents,
                    listing.total_price_currency,
                    listing.image_url,
                    listing.favourite_count,
                    listing.view_count,
                    listing.user_id,
                    listing.user_login,
                    listing.user_profile_url,
                    listing.created_at_ts,
                    primary_catalog_id,
                    primary_root_catalog_id,
                    discovered_at,
                    discovered_at,
                    run_id,
                    json.dumps(listing.raw_card, ensure_ascii=False, sort_keys=True),
                ),
            )

    def record_listing_discovery(
        self,
        *,
        run_id: str,
        listing: ListingCard,
        observed_at: str,
        source_catalog_id: int,
        source_page_number: int,
        card_position: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO listing_discoveries (
                    run_id, listing_id, observed_at, source_catalog_id,
                    source_page_number, source_url, card_position, raw_card_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    listing.listing_id,
                    observed_at,
                    source_catalog_id,
                    source_page_number,
                    listing.source_url,
                    card_position,
                    json.dumps(listing.raw_card, ensure_ascii=False, sort_keys=True),
                ),
            )

    def record_listing_observation(
        self,
        *,
        run_id: str,
        listing: ListingCard,
        observed_at: str,
        source_catalog_id: int,
        source_page_number: int,
        card_position: int,
    ) -> None:
        payload_json = json.dumps(listing.raw_card, ensure_ascii=False, sort_keys=True)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO listing_observations (
                    run_id, listing_id, observed_at, canonical_url, source_url,
                    source_catalog_id, source_page_number, first_card_position, sighting_count,
                    title, brand, size_label, condition_label,
                    price_amount_cents, price_currency,
                    total_price_amount_cents, total_price_currency,
                    image_url, raw_card_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, listing_id) DO UPDATE SET
                    observed_at = CASE
                        WHEN excluded.observed_at < listing_observations.observed_at THEN excluded.observed_at
                        ELSE listing_observations.observed_at
                    END,
                    source_catalog_id = CASE
                        WHEN excluded.observed_at < listing_observations.observed_at THEN excluded.source_catalog_id
                        ELSE listing_observations.source_catalog_id
                    END,
                    source_page_number = CASE
                        WHEN excluded.observed_at < listing_observations.observed_at THEN excluded.source_page_number
                        ELSE listing_observations.source_page_number
                    END,
                    first_card_position = CASE
                        WHEN excluded.first_card_position < listing_observations.first_card_position THEN excluded.first_card_position
                        ELSE listing_observations.first_card_position
                    END,
                    sighting_count = listing_observations.sighting_count + 1,
                    title = COALESCE(listing_observations.title, excluded.title),
                    brand = COALESCE(listing_observations.brand, excluded.brand),
                    size_label = COALESCE(listing_observations.size_label, excluded.size_label),
                    condition_label = COALESCE(listing_observations.condition_label, excluded.condition_label),
                    price_amount_cents = COALESCE(listing_observations.price_amount_cents, excluded.price_amount_cents),
                    price_currency = COALESCE(listing_observations.price_currency, excluded.price_currency),
                    total_price_amount_cents = COALESCE(listing_observations.total_price_amount_cents, excluded.total_price_amount_cents),
                    total_price_currency = COALESCE(listing_observations.total_price_currency, excluded.total_price_currency),
                    image_url = COALESCE(listing_observations.image_url, excluded.image_url)
                """,
                (
                    run_id,
                    listing.listing_id,
                    observed_at,
                    listing.canonical_url,
                    listing.source_url,
                    source_catalog_id,
                    source_page_number,
                    card_position,
                    listing.title,
                    listing.brand,
                    listing.size_label,
                    listing.condition_label,
                    listing.price_amount_cents,
                    listing.price_currency,
                    listing.total_price_amount_cents,
                    listing.total_price_currency,
                    listing.image_url,
                    payload_json,
                ),
            )

    def latest_run(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM discovery_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

    def start_runtime_cycle(
        self,
        *,
        mode: str,
        phase: str,
        interval_seconds: float | None,
        state_probe_limit: int,
        config: dict[str, object],
    ) -> str:
        cycle_id = datetime.now(UTC).strftime("cycle-%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        started_at = _utc_now()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO runtime_cycles (
                    cycle_id, started_at, mode, status, phase, interval_seconds,
                    state_probe_limit, config_json
                ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    started_at,
                    mode,
                    phase,
                    interval_seconds,
                    state_probe_limit,
                    _serialize_runtime_config(config),
                ),
            )
            self._upsert_runtime_controller_state(
                status="running",
                phase=phase,
                mode=mode,
                active_cycle_id=cycle_id,
                latest_cycle_id=cycle_id,
                interval_seconds=interval_seconds,
                updated_at=started_at,
                paused_at=None,
                next_resume_at=None,
                last_error=None,
                last_error_at=None,
                requested_action="none",
                requested_at=None,
                config=config,
            )
        return cycle_id

    def update_runtime_cycle_phase(self, cycle_id: str, *, phase: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE runtime_cycles SET phase = ? WHERE cycle_id = ?",
                (phase, cycle_id),
            )
            controller_row = self._runtime_controller_row()
            if controller_row is not None and controller_row["active_cycle_id"] == cycle_id:
                self._upsert_runtime_controller_state(
                    phase=phase,
                    updated_at=_utc_now(),
                )

    def complete_runtime_cycle(
        self,
        cycle_id: str,
        *,
        status: str,
        phase: str,
        discovery_run_id: str | None = None,
        state_probed_count: int = 0,
        tracked_listings: int = 0,
        freshness_counts: dict[str, object] | None = None,
        last_error: str | None = None,
    ) -> None:
        freshness_counts = freshness_counts or {}
        finished_at = _utc_now()
        with self.connection:
            cycle_row = self.connection.execute(
                "SELECT * FROM runtime_cycles WHERE cycle_id = ?",
                (cycle_id,),
            ).fetchone()
            self.connection.execute(
                """
                UPDATE runtime_cycles
                SET finished_at = ?, status = ?, phase = ?, discovery_run_id = ?,
                    state_probed_count = ?, tracked_listings = ?,
                    first_pass_only = ?, fresh_followup = ?, aging_followup = ?, stale_followup = ?,
                    last_error = ?
                WHERE cycle_id = ?
                """,
                (
                    finished_at,
                    status,
                    phase,
                    discovery_run_id,
                    state_probed_count,
                    tracked_listings,
                    int(freshness_counts.get("first-pass-only", 0) or 0),
                    int(freshness_counts.get("fresh-followup", 0) or 0),
                    int(freshness_counts.get("aging-followup", 0) or 0),
                    int(freshness_counts.get("stale-followup", 0) or 0),
                    last_error,
                    cycle_id,
                ),
            )
            if cycle_row is not None:
                controller_status = _controller_status_from_runtime_cycle_status(status)
                controller_phase = _controller_phase_from_runtime_state(controller_status, phase)
                self._upsert_runtime_controller_state(
                    status=controller_status,
                    phase=controller_phase,
                    mode=cycle_row["mode"],
                    active_cycle_id=None,
                    latest_cycle_id=cycle_id,
                    interval_seconds=cycle_row["interval_seconds"],
                    updated_at=finished_at,
                    paused_at=None if controller_status != "paused" else _UNSET,
                    next_resume_at=None if controller_status != "scheduled" else _UNSET,
                    last_error=last_error,
                    last_error_at=None if last_error is None else finished_at,
                    config=_deserialize_runtime_config(cycle_row["config_json"]),
                )

    def runtime_cycle(self, cycle_id: str) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT * FROM runtime_cycles WHERE cycle_id = ?",
            (cycle_id,),
        ).fetchone()
        if row is None:
            return None
        return self._hydrate_runtime_cycle_row(row)

    def runtime_controller_state(self, *, now: str | None = None) -> dict[str, object] | None:
        row = self._runtime_controller_row()
        if row is None:
            return None
        return self._hydrate_runtime_controller_row(row, now_dt=_coerce_now(now))

    def set_runtime_controller_state(
        self,
        *,
        status: str | object = _UNSET,
        phase: str | object = _UNSET,
        mode: str | None | object = _UNSET,
        active_cycle_id: str | None | object = _UNSET,
        latest_cycle_id: str | None | object = _UNSET,
        interval_seconds: float | None | object = _UNSET,
        updated_at: str | None | object = _UNSET,
        paused_at: str | None | object = _UNSET,
        next_resume_at: str | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        last_error_at: str | None | object = _UNSET,
        requested_action: str | object = _UNSET,
        requested_at: str | None | object = _UNSET,
        config: dict[str, object] | object = _UNSET,
    ) -> dict[str, object]:
        with self.connection:
            self._upsert_runtime_controller_state(
                status=status,
                phase=phase,
                mode=mode,
                active_cycle_id=active_cycle_id,
                latest_cycle_id=latest_cycle_id,
                interval_seconds=interval_seconds,
                updated_at=updated_at,
                paused_at=paused_at,
                next_resume_at=next_resume_at,
                last_error=last_error,
                last_error_at=last_error_at,
                requested_action=requested_action,
                requested_at=requested_at,
                config=config,
            )
            row = self._runtime_controller_row()
        if row is None:
            raise RuntimeError("Runtime controller state was not persisted.")
        reference_now = updated_at if isinstance(updated_at, str) else None
        return self._hydrate_runtime_controller_row(row, now_dt=_coerce_now(reference_now))

    def request_runtime_pause(self, *, requested_at: str | None = None) -> dict[str, object]:
        request_time = requested_at or _utc_now()
        controller = self.runtime_controller_state(now=request_time)
        if controller is not None and controller.get("status") in {"scheduled", "paused"} and controller.get("mode") == "continuous":
            paused_at = controller.get("paused_at") or request_time
            return self.set_runtime_controller_state(
                status="paused",
                phase="paused",
                updated_at=request_time,
                paused_at=None if paused_at is None else str(paused_at),
                next_resume_at=None,
                requested_action="none",
                requested_at=None,
            )
        return self.set_runtime_controller_state(
            requested_action="pause",
            requested_at=request_time,
            updated_at=request_time,
        )

    def request_runtime_resume(self, *, requested_at: str | None = None) -> dict[str, object]:
        request_time = requested_at or _utc_now()
        controller = self.runtime_controller_state(now=request_time)
        if controller is not None and controller.get("status") == "paused" and controller.get("mode") == "continuous":
            return self.set_runtime_controller_state(
                status="scheduled",
                phase="waiting",
                updated_at=request_time,
                paused_at=None,
                next_resume_at=request_time,
                requested_action="none",
                requested_at=None,
            )
        if controller is not None and controller.get("requested_action") == "pause":
            return self.clear_runtime_controller_action(updated_at=request_time)
        return self.set_runtime_controller_state(
            requested_action="resume",
            requested_at=request_time,
            updated_at=request_time,
        )

    def clear_runtime_controller_action(self, *, updated_at: str | None = None) -> dict[str, object]:
        return self.set_runtime_controller_state(
            requested_action="none",
            requested_at=None,
            updated_at=updated_at if updated_at is not None else _utc_now(),
        )

    def runtime_status(self, *, limit: int = 10, now: str | None = None) -> dict[str, object]:
        now_dt = _coerce_now(now)
        generated_at = now_dt.replace(microsecond=0).isoformat()
        bounded_limit = max(int(limit), 1)
        recent_cycles = [
            self._hydrate_runtime_cycle_row(row)
            for row in self.connection.execute(
                "SELECT * FROM runtime_cycles ORDER BY started_at DESC, cycle_id DESC LIMIT ?",
                (bounded_limit,),
            )
        ]
        recent_failures = [
            self._hydrate_runtime_cycle_row(row)
            for row in self.connection.execute(
                "SELECT * FROM runtime_cycles WHERE status = 'failed' ORDER BY started_at DESC, cycle_id DESC LIMIT ?",
                (bounded_limit,),
            )
        ]
        totals_row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_cycles,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_cycles,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_cycles,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_cycles,
                SUM(CASE WHEN status = 'interrupted' THEN 1 ELSE 0 END) AS interrupted_cycles
            FROM runtime_cycles
            """
        ).fetchone()
        totals = dict(totals_row) if totals_row is not None else {}
        latest_cycle = None if not recent_cycles else recent_cycles[0]
        controller = self.runtime_controller_state(now=generated_at)
        effective_status = None
        effective_phase = None
        effective_mode = None
        effective_updated_at = None
        effective_paused_at = None
        effective_next_resume_at = None
        effective_elapsed_pause_seconds = None
        effective_next_resume_in_seconds = None
        effective_last_error = None
        effective_last_error_at = None
        effective_requested_action = None
        effective_requested_at = None
        effective_active_cycle_id = None
        effective_latest_cycle_id = None
        heartbeat = None
        if controller is not None:
            effective_status = controller.get("status")
            effective_phase = controller.get("phase")
            effective_mode = controller.get("mode") or (None if latest_cycle is None else latest_cycle.get("mode"))
            effective_updated_at = controller.get("updated_at")
            effective_paused_at = controller.get("paused_at")
            effective_next_resume_at = controller.get("next_resume_at")
            effective_elapsed_pause_seconds = controller.get("elapsed_pause_seconds")
            effective_next_resume_in_seconds = controller.get("next_resume_in_seconds")
            effective_last_error = controller.get("last_error")
            effective_last_error_at = controller.get("last_error_at")
            effective_requested_action = controller.get("requested_action")
            effective_requested_at = controller.get("requested_at")
            effective_active_cycle_id = controller.get("active_cycle_id")
            effective_latest_cycle_id = controller.get("latest_cycle_id")
            heartbeat = controller.get("heartbeat")
        elif latest_cycle is not None:
            effective_status = _controller_status_from_runtime_cycle_status(str(latest_cycle.get("status") or ""))
            effective_phase = latest_cycle.get("phase")
            effective_mode = latest_cycle.get("mode")

        return {
            "generated_at": generated_at,
            "db_path": str(self.db_path),
            "controller": controller,
            "status": effective_status,
            "phase": effective_phase,
            "mode": effective_mode,
            "updated_at": effective_updated_at,
            "paused_at": effective_paused_at,
            "next_resume_at": effective_next_resume_at,
            "elapsed_pause_seconds": effective_elapsed_pause_seconds,
            "next_resume_in_seconds": effective_next_resume_in_seconds,
            "last_error": effective_last_error if effective_last_error is not None else (None if not recent_failures else recent_failures[0].get("last_error")),
            "last_error_at": effective_last_error_at,
            "requested_action": effective_requested_action,
            "requested_at": effective_requested_at,
            "active_cycle_id": effective_active_cycle_id,
            "latest_cycle_id": effective_latest_cycle_id,
            "heartbeat": heartbeat,
            "latest_cycle": latest_cycle,
            "recent_cycles": recent_cycles,
            "latest_failure": None if not recent_failures else recent_failures[0],
            "recent_failures": recent_failures,
            "totals": {
                "total_cycles": int(totals.get("total_cycles") or 0),
                "completed_cycles": int(totals.get("completed_cycles") or 0),
                "failed_cycles": int(totals.get("failed_cycles") or 0),
                "running_cycles": int(totals.get("running_cycles") or 0),
                "interrupted_cycles": int(totals.get("interrupted_cycles") or 0),
            },
        }

    def count_rows(self, table_name: str) -> int:
        row = self.connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])

    def coverage_summary(self, run_id: str | None = None) -> dict[str, object] | None:
        run = self._resolve_run(run_id)
        if run is None:
            return None

        by_root = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT
                    catalogs.root_title AS root_title,
                    SUM(CASE WHEN catalogs.is_leaf = 1 THEN 1 ELSE 0 END) AS total_leaf_catalogs,
                    COUNT(DISTINCT CASE WHEN catalog_scans.run_id = ? THEN catalogs.catalog_id END) AS scanned_leaf_catalogs,
                    COALESCE(SUM(CASE WHEN catalog_scans.run_id = ? AND catalog_scans.success = 1 THEN 1 ELSE 0 END), 0) AS successful_scans,
                    COALESCE(SUM(CASE WHEN catalog_scans.run_id = ? AND catalog_scans.success = 0 THEN 1 ELSE 0 END), 0) AS failed_scans,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM listing_discoveries discoveries
                        JOIN catalogs discovery_catalogs ON discovery_catalogs.catalog_id = discoveries.source_catalog_id
                        WHERE discoveries.run_id = ? AND discovery_catalogs.root_title = catalogs.root_title
                    ), 0) AS listing_sightings,
                    COALESCE((
                        SELECT COUNT(DISTINCT discoveries.listing_id)
                        FROM listing_discoveries discoveries
                        JOIN catalogs discovery_catalogs ON discovery_catalogs.catalog_id = discoveries.source_catalog_id
                        WHERE discoveries.run_id = ? AND discovery_catalogs.root_title = catalogs.root_title
                    ), 0) AS unique_listings
                FROM catalogs
                LEFT JOIN catalog_scans ON catalog_scans.catalog_id = catalogs.catalog_id AND catalog_scans.run_id = ?
                GROUP BY catalogs.root_title
                ORDER BY catalogs.root_title
                """,
                (run["run_id"], run["run_id"], run["run_id"], run["run_id"], run["run_id"], run["run_id"]),
            )
            if row["root_title"] in {"Femmes", "Hommes"}
        ]

        failures = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT catalogs.path AS catalog_path, catalog_scans.page_number, catalog_scans.response_status, catalog_scans.error_message
                FROM catalog_scans
                JOIN catalogs ON catalogs.catalog_id = catalog_scans.catalog_id
                WHERE catalog_scans.run_id = ? AND catalog_scans.success = 0
                ORDER BY catalogs.root_title, catalogs.path, catalog_scans.page_number
                LIMIT 20
                """,
                (run["run_id"],),
            )
        ]

        return {"run": dict(run), "by_root": by_root, "failures": failures}

    def listing_history(self, listing_id: int, *, now: str | None = None, limit: int = 20) -> dict[str, object] | None:
        summaries = self.listing_history_summaries(now=now, listing_id=listing_id)
        if not summaries:
            return None
        summary = summaries[0]
        rows = self.connection.execute(
            """
            SELECT
                observations.run_id,
                observations.listing_id,
                observations.observed_at,
                observations.canonical_url,
                observations.source_url,
                observations.source_catalog_id,
                observations.source_page_number,
                observations.first_card_position,
                observations.sighting_count,
                observations.title,
                observations.brand,
                observations.size_label,
                observations.condition_label,
                observations.price_amount_cents,
                observations.price_currency,
                observations.total_price_amount_cents,
                observations.total_price_currency,
                observations.image_url,
                observations.raw_card_payload_json,
                catalogs.path AS catalog_path,
                catalogs.root_title AS root_title
            FROM listing_observations AS observations
            LEFT JOIN catalogs ON catalogs.catalog_id = observations.source_catalog_id
            WHERE observations.listing_id = ?
            ORDER BY observations.observed_at DESC, observations.run_id DESC
            LIMIT ?
            """,
            (listing_id, limit),
        ).fetchall()
        timeline = [self._hydrate_observation_row(row) for row in rows]
        return {"summary": summary, "timeline": timeline}

    def listing_history_summaries(self, *, now: str | None = None, listing_id: int | None = None) -> list[dict[str, object]]:
        now_dt = _coerce_now(now)
        params: list[object] = []
        listing_filter = ""
        if listing_id is not None:
            listing_filter = "WHERE observations.listing_id = ?"
            params.append(listing_id)

        rows = self.connection.execute(
            f"""
            WITH summary AS (
                SELECT
                    observations.listing_id AS listing_id,
                    COUNT(*) AS observation_count,
                    SUM(observations.sighting_count) AS total_sightings,
                    MIN(observations.observed_at) AS first_seen_at,
                    MAX(observations.observed_at) AS last_seen_at,
                    AVG(CASE
                        WHEN previous_observed_at IS NULL THEN NULL
                        ELSE (julianday(observed_at) - julianday(previous_observed_at)) * 24.0
                    END) AS average_revisit_hours
                FROM (
                    SELECT
                        listing_observations.*,
                        LAG(listing_observations.observed_at) OVER (
                            PARTITION BY listing_observations.listing_id
                            ORDER BY listing_observations.observed_at
                        ) AS previous_observed_at
                    FROM listing_observations
                ) AS observations
                {listing_filter}
                GROUP BY observations.listing_id
            )
            SELECT
                summary.listing_id,
                summary.observation_count,
                summary.total_sightings,
                summary.first_seen_at,
                summary.last_seen_at,
                summary.average_revisit_hours,
                listings.canonical_url,
                listings.title,
                listings.brand,
                listings.size_label,
                listings.condition_label,
                listings.price_amount_cents,
                listings.price_currency,
                listings.total_price_amount_cents,
                listings.total_price_currency,
                listings.image_url,
                roots.title AS root_title
            FROM summary
            JOIN listings ON listings.listing_id = summary.listing_id
            LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
            ORDER BY summary.last_seen_at DESC, summary.listing_id DESC
            """,
            params,
        ).fetchall()

        summaries: list[dict[str, object]] = []
        for row in rows:
            summary = dict(row)
            age_hours = _hours_between(summary["last_seen_at"], now_dt)
            freshness_bucket = _freshness_bucket(int(summary["observation_count"]), age_hours)
            signal_completeness = _signal_completeness(summary)
            summary.update(
                {
                    "last_seen_age_hours": round(age_hours, 2),
                    "freshness_bucket": freshness_bucket,
                    "signal_completeness": signal_completeness,
                    "average_revisit_hours": None
                    if summary["average_revisit_hours"] is None
                    else round(float(summary["average_revisit_hours"]), 2),
                }
            )
            summaries.append(summary)
        return summaries

    def explorer_filter_options(self) -> dict[str, list[dict[str, object]] | int]:
        tracked_predicate = "EXISTS (SELECT 1 FROM listing_observations WHERE listing_observations.listing_id = listings.listing_id)"
        tracked_listings_row = self.connection.execute(
            f"SELECT COUNT(*) AS tracked_listings FROM listings WHERE {tracked_predicate}"
        ).fetchone()
        tracked_listings = 0 if tracked_listings_row is None else int(tracked_listings_row["tracked_listings"] or 0)

        roots = [
            {
                "value": str(row["root_title"]),
                "label": f"{row['root_title']} ({row['count']})",
                "count": int(row["count"]),
            }
            for row in self.connection.execute(
                f"""
                SELECT COALESCE(roots.title, 'Unknown') AS root_title, COUNT(*) AS count
                FROM listings
                LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
                WHERE {tracked_predicate}
                GROUP BY COALESCE(roots.title, 'Unknown')
                ORDER BY COALESCE(roots.title, 'Unknown')
                """
            )
        ]
        catalogs = [
            {
                "value": str(row["catalog_id"]),
                "catalog_id": int(row["catalog_id"]),
                "label": f"{row['catalog_path']} ({row['count']})",
                "count": int(row["count"]),
            }
            for row in self.connection.execute(
                f"""
                SELECT
                    listings.primary_catalog_id AS catalog_id,
                    COALESCE(primary_catalog.path, COALESCE(roots.title, 'Unknown')) AS catalog_path,
                    COUNT(*) AS count
                FROM listings
                LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
                LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
                WHERE listings.primary_catalog_id IS NOT NULL
                  AND {tracked_predicate}
                GROUP BY listings.primary_catalog_id, COALESCE(primary_catalog.path, COALESCE(roots.title, 'Unknown'))
                ORDER BY COALESCE(primary_catalog.path, COALESCE(roots.title, 'Unknown'))
                """
            )
        ]
        brands = [
            {
                "value": str(row["brand_label"]),
                "label": f"{row['brand_label']} ({row['count']})",
                "count": int(row["count"]),
            }
            for row in self.connection.execute(
                f"""
                SELECT COALESCE(listings.brand, 'Unknown brand') AS brand_label, COUNT(*) AS count
                FROM listings
                WHERE {tracked_predicate}
                GROUP BY COALESCE(listings.brand, 'Unknown brand')
                ORDER BY count DESC, brand_label ASC
                LIMIT 80
                """
            )
        ]
        conditions = [
            {
                "value": str(row["condition_label"]),
                "label": f"{row['condition_label']} ({row['count']})",
                "count": int(row["count"]),
            }
            for row in self.connection.execute(
                f"""
                SELECT COALESCE(listings.condition_label, 'Unknown condition') AS condition_label, COUNT(*) AS count
                FROM listings
                WHERE {tracked_predicate}
                GROUP BY COALESCE(listings.condition_label, 'Unknown condition')
                ORDER BY count DESC, condition_label ASC
                LIMIT 40
                """
            )
        ]
        return {
            "tracked_listings": tracked_listings,
            "roots": [{"value": "all", "label": "All roots"}] + roots,
            "catalogs": [{"value": "", "label": "All catalogs"}] + catalogs,
            "brands": [{"value": "all", "label": "All brands"}] + brands,
            "conditions": [{"value": "all", "label": "All conditions"}] + conditions,
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

    def listing_explorer_page(
        self,
        *,
        root: str | None = None,
        catalog_id: int | None = None,
        brand: str | None = None,
        condition: str | None = None,
        query: str | None = None,
        sort: str = "last_seen_desc",
        page: int = 1,
        page_size: int = 50,
        now: str | None = None,
    ) -> dict[str, object]:
        now_dt = _coerce_now(now)
        bounded_page = max(int(page), 1)
        bounded_page_size = max(1, min(int(page_size), 100))
        offset = (bounded_page - 1) * bounded_page_size

        order_by = {
            "last_seen_desc": "listings.last_discovered_at DESC, listings.listing_id DESC",
            "price_desc": "listings.price_amount_cents IS NULL, listings.price_amount_cents DESC, listings.last_discovered_at DESC, listings.listing_id DESC",
            "price_asc": "listings.price_amount_cents IS NULL, listings.price_amount_cents ASC, listings.last_discovered_at DESC, listings.listing_id DESC",
            "favourite_desc": "listings.favourite_count IS NULL, listings.favourite_count DESC, listings.last_discovered_at DESC, listings.listing_id DESC",
            "view_desc": "listings.view_count IS NULL, listings.view_count DESC, listings.last_discovered_at DESC, listings.listing_id DESC",
            "created_at_desc": "listings.created_at_ts IS NULL, listings.created_at_ts DESC, listings.last_discovered_at DESC, listings.listing_id DESC",
            "first_seen_desc": "listings.first_discovered_at DESC, listings.listing_id DESC",
        }.get(sort, "listings.last_discovered_at DESC, listings.listing_id DESC")
        sort_key = sort if sort in {
            "last_seen_desc",
            "price_desc",
            "price_asc",
            "favourite_desc",
            "view_desc",
            "created_at_desc",
            "first_seen_desc",
        } else "last_seen_desc"

        where_clauses = [
            "EXISTS (SELECT 1 FROM listing_observations WHERE listing_observations.listing_id = listings.listing_id)"
        ]
        params: list[object] = []
        if root:
            where_clauses.append("COALESCE(roots.title, 'Unknown') = ?")
            params.append(root)
        if catalog_id is not None:
            where_clauses.append("listings.primary_catalog_id = ?")
            params.append(catalog_id)
        if brand:
            where_clauses.append("COALESCE(listings.brand, 'Unknown brand') = ?")
            params.append(brand)
        if condition:
            where_clauses.append("COALESCE(listings.condition_label, 'Unknown condition') = ?")
            params.append(condition)
        cleaned_query = _clean_query_text(query)
        if cleaned_query:
            like_query = f"%{cleaned_query}%"
            where_clauses.append(
                "("
                "CAST(listings.listing_id AS TEXT) LIKE ? "
                "OR LOWER(COALESCE(listings.title, '')) LIKE ? "
                "OR LOWER(COALESCE(listings.brand, '')) LIKE ? "
                "OR LOWER(COALESCE(primary_catalog.path, '')) LIKE ? "
                "OR LOWER(COALESCE(listings.user_login, '')) LIKE ?"
                ")"
            )
            params.extend([like_query, like_query, like_query, like_query, like_query])
        where_sql = "WHERE " + " AND ".join(where_clauses)

        total_row = self.connection.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM listings
            LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            {where_sql}
            """,
            params,
        ).fetchone()
        total_listings = 0 if total_row is None else int(total_row["total"] or 0)

        rows = self.connection.execute(
            f"""
            SELECT
                listings.listing_id,
                listings.canonical_url,
                listings.source_url,
                listings.title,
                listings.brand,
                listings.size_label,
                listings.condition_label,
                listings.price_amount_cents,
                listings.price_currency,
                listings.total_price_amount_cents,
                listings.total_price_currency,
                listings.image_url,
                listings.favourite_count,
                listings.view_count,
                listings.user_id,
                listings.user_login,
                listings.user_profile_url,
                listings.created_at_ts,
                listings.first_discovered_at,
                listings.last_discovered_at,
                roots.title AS root_title,
                listings.primary_catalog_id,
                COALESCE(primary_catalog.path, COALESCE(roots.title, 'Unknown')) AS primary_catalog_path
            FROM listings
            LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, bounded_page_size, offset],
        ).fetchall()

        page_listing_ids = [int(row["listing_id"]) for row in rows]
        summaries_by_listing_id: dict[int, dict[str, object]] = {}
        probes_by_listing_id: dict[int, dict[str, object]] = {}
        if page_listing_ids:
            placeholders = ", ".join("?" for _ in page_listing_ids)
            summary_rows = self.connection.execute(
                f"""
                WITH ordered_observations AS (
                    SELECT
                        listing_observations.listing_id,
                        listing_observations.observed_at,
                        listing_observations.sighting_count,
                        LAG(listing_observations.observed_at) OVER (
                            PARTITION BY listing_observations.listing_id
                            ORDER BY listing_observations.observed_at
                        ) AS previous_observed_at
                    FROM listing_observations
                    WHERE listing_observations.listing_id IN ({placeholders})
                )
                SELECT
                    ordered_observations.listing_id,
                    COUNT(*) AS observation_count,
                    SUM(ordered_observations.sighting_count) AS total_sightings,
                    MIN(ordered_observations.observed_at) AS first_seen_at,
                    MAX(ordered_observations.observed_at) AS last_seen_at,
                    AVG(CASE
                        WHEN ordered_observations.previous_observed_at IS NULL THEN NULL
                        ELSE (julianday(ordered_observations.observed_at) - julianday(ordered_observations.previous_observed_at)) * 24.0
                    END) AS average_revisit_hours
                FROM ordered_observations
                GROUP BY ordered_observations.listing_id
                """,
                page_listing_ids,
            ).fetchall()
            summaries_by_listing_id = {
                int(row["listing_id"]): dict(row)
                for row in summary_rows
            }

            probe_rows = self.connection.execute(
                f"""
                SELECT
                    ranked.listing_id,
                    ranked.probed_at,
                    ranked.response_status,
                    ranked.probe_outcome
                FROM (
                    SELECT
                        item_page_probes.listing_id,
                        item_page_probes.probed_at,
                        item_page_probes.response_status,
                        item_page_probes.probe_outcome,
                        ROW_NUMBER() OVER (
                            PARTITION BY item_page_probes.listing_id
                            ORDER BY item_page_probes.probed_at DESC, item_page_probes.probe_id DESC
                        ) AS probe_rank
                    FROM item_page_probes
                    WHERE item_page_probes.listing_id IN ({placeholders})
                ) AS ranked
                WHERE ranked.probe_rank = 1
                """,
                page_listing_ids,
            ).fetchall()
            probes_by_listing_id = {
                int(row["listing_id"]): dict(row)
                for row in probe_rows
            }

        items: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            listing_id = int(item["listing_id"])
            summary = summaries_by_listing_id.get(listing_id, {})
            latest_probe = probes_by_listing_id.get(listing_id, {})
            item["observation_count"] = int(summary.get("observation_count") or 0)
            item["total_sightings"] = int(summary.get("total_sightings") or 0)
            item["first_seen_at"] = summary.get("first_seen_at") or item.get("first_discovered_at")
            item["last_seen_at"] = summary.get("last_seen_at") or item.get("last_discovered_at")
            item["average_revisit_hours"] = (
                None
                if summary.get("average_revisit_hours") is None
                else round(float(summary["average_revisit_hours"]), 2)
            )
            item["latest_probe_at"] = latest_probe.get("probed_at")
            item["latest_probe_response_status"] = latest_probe.get("response_status")
            item["latest_probe_outcome"] = latest_probe.get("probe_outcome")
            age_hours = _hours_between(str(item["last_seen_at"]), now_dt)
            item["last_seen_age_hours"] = round(age_hours, 2)
            item["freshness_bucket"] = _freshness_bucket(int(item["observation_count"]), age_hours)
            item["signal_completeness"] = _signal_completeness(item)
            items.append(item)

        total_pages = 0 if total_listings == 0 else ((total_listings - 1) // bounded_page_size) + 1
        return {
            "page": bounded_page,
            "page_size": bounded_page_size,
            "total_listings": total_listings,
            "total_pages": total_pages,
            "has_previous_page": bounded_page > 1,
            "has_next_page": offset + len(items) < total_listings,
            "sort": sort_key,
            "items": items,
        }

    def freshness_summary(self, *, now: str | None = None) -> dict[str, object]:
        summaries = self.listing_history_summaries(now=now)
        generated_at = _coerce_now(now).replace(microsecond=0).isoformat()
        overall = _empty_freshness_bucket_counts()
        overall["tracked_listings"] = len(summaries)
        by_root: dict[str, dict[str, int | str]] = {}

        for summary in summaries:
            bucket = str(summary["freshness_bucket"])
            overall[bucket] += 1
            root_title = str(summary.get("root_title") or "Unknown")
            if root_title not in by_root:
                by_root[root_title] = _empty_freshness_bucket_counts(root_title=root_title)
            by_root[root_title]["tracked_listings"] += 1
            by_root[root_title][bucket] += 1

        return {
            "generated_at": generated_at,
            "overall": overall,
            "by_root": sorted(by_root.values(), key=lambda row: str(row["root_title"])),
        }

    def revisit_candidates(self, *, limit: int = 20, now: str | None = None) -> list[dict[str, object]]:
        summaries = self.listing_history_summaries(now=now)
        candidates: list[dict[str, object]] = []
        for summary in summaries:
            age_hours = float(summary["last_seen_age_hours"])
            observation_count = int(summary["observation_count"])
            signal_completeness = int(summary["signal_completeness"])
            under_observed_boost = 18.0 if observation_count == 1 else 8.0 if observation_count == 2 else 0.0
            stale_boost = 12.0 if age_hours > STALE_FOLLOWUP_HOURS else 6.0 if age_hours > FRESH_FOLLOWUP_HOURS else 0.0
            priority_score = round(age_hours + under_observed_boost + stale_boost + (signal_completeness * 1.5), 2)
            reasons = [str(summary["freshness_bucket"])]
            reasons.append("under-observed" if observation_count <= 2 else "tracked")
            reasons.append("high-signal" if signal_completeness >= 5 else "thin-signal")
            candidate = dict(summary)
            candidate.update({"priority_score": priority_score, "priority_reasons": reasons})
            candidates.append(candidate)

        candidates.sort(
            key=lambda item: (
                -float(item["priority_score"]),
                -int(item["signal_completeness"]),
                str(item["last_seen_at"]),
                int(item["listing_id"]),
            )
        )
        return candidates[:limit]

    def record_item_page_probe(
        self,
        *,
        listing_id: int,
        probed_at: str,
        requested_url: str,
        final_url: str | None,
        response_status: int | None,
        probe_outcome: str,
        detail: dict[str, object],
        error_message: str | None,
    ) -> str:
        probe_id = datetime.now(UTC).strftime("probe-%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO item_page_probes (
                    probe_id, listing_id, probed_at, requested_url, final_url,
                    response_status, probe_outcome, detail_json, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    probe_id,
                    listing_id,
                    probed_at,
                    requested_url,
                    final_url,
                    response_status,
                    probe_outcome,
                    json.dumps(detail, ensure_ascii=False, sort_keys=True),
                    error_message,
                ),
            )
        return probe_id

    def latest_item_page_probe(self, listing_id: int) -> dict[str, object] | None:
        row = self.connection.execute(
            """
            SELECT probe_id, listing_id, probed_at, requested_url, final_url, response_status, probe_outcome, detail_json, error_message
            FROM item_page_probes
            WHERE listing_id = ?
            ORDER BY probed_at DESC, probe_id DESC
            LIMIT 1
            """,
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        probe = dict(row)
        detail_json = probe.pop("detail_json")
        probe["detail"] = json.loads(detail_json) if detail_json else {}
        return probe

    def listing_state_inputs(self, *, now: str | None = None, listing_id: int | None = None) -> list[dict[str, object]]:
        now_dt = _coerce_now(now)
        observation_filter = ""
        probe_filter = ""
        params: list[object] = []
        if listing_id is not None:
            observation_filter = "WHERE listing_observations.listing_id = ?"
            probe_filter = "WHERE item_page_probes.listing_id = ?"
            params = [listing_id, listing_id]

        rows = self.connection.execute(
            f"""
            WITH ordered_observations AS (
                SELECT
                    listing_observations.*,
                    LAG(listing_observations.observed_at) OVER (
                        PARTITION BY listing_observations.listing_id
                        ORDER BY listing_observations.observed_at
                    ) AS previous_observed_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY listing_observations.listing_id
                        ORDER BY listing_observations.observed_at DESC, listing_observations.run_id DESC
                    ) AS observation_recency_rank
                FROM listing_observations
                {observation_filter}
            ),
            summary AS (
                SELECT
                    ordered_observations.listing_id AS listing_id,
                    COUNT(*) AS observation_count,
                    SUM(ordered_observations.sighting_count) AS total_sightings,
                    MIN(ordered_observations.observed_at) AS first_seen_at,
                    MAX(ordered_observations.observed_at) AS last_seen_at,
                    AVG(CASE
                        WHEN ordered_observations.previous_observed_at IS NULL THEN NULL
                        ELSE (julianday(ordered_observations.observed_at) - julianday(ordered_observations.previous_observed_at)) * 24.0
                    END) AS average_revisit_hours,
                    MAX(CASE WHEN ordered_observations.observation_recency_rank = 1 THEN ordered_observations.run_id END) AS last_observed_run_id
                FROM ordered_observations
                GROUP BY ordered_observations.listing_id
            ),
            latest_primary_scan AS (
                SELECT catalog_id, run_id, fetched_at
                FROM (
                    SELECT
                        catalog_scans.catalog_id,
                        catalog_scans.run_id,
                        catalog_scans.fetched_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY catalog_scans.catalog_id
                            ORDER BY catalog_scans.fetched_at DESC, catalog_scans.run_id DESC
                        ) AS scan_rank
                    FROM catalog_scans
                    WHERE catalog_scans.success = 1
                )
                WHERE scan_rank = 1
            ),
            follow_up_miss AS (
                SELECT
                    listings.listing_id AS listing_id,
                    COUNT(DISTINCT scans.run_id) AS follow_up_miss_count,
                    MAX(scans.fetched_at) AS latest_follow_up_miss_at
                FROM summary
                JOIN listings ON listings.listing_id = summary.listing_id
                LEFT JOIN catalog_scans AS scans
                  ON scans.catalog_id = listings.primary_catalog_id
                 AND scans.success = 1
                 AND scans.fetched_at > summary.last_seen_at
                LEFT JOIN listing_observations AS observations
                  ON observations.listing_id = summary.listing_id
                 AND observations.run_id = scans.run_id
                WHERE observations.run_id IS NULL
                GROUP BY listings.listing_id
            ),
            latest_probe AS (
                SELECT
                    probe_id,
                    listing_id,
                    probed_at,
                    requested_url,
                    final_url,
                    response_status,
                    probe_outcome,
                    detail_json,
                    error_message
                FROM (
                    SELECT
                        item_page_probes.probe_id,
                        item_page_probes.listing_id,
                        item_page_probes.probed_at,
                        item_page_probes.requested_url,
                        item_page_probes.final_url,
                        item_page_probes.response_status,
                        item_page_probes.probe_outcome,
                        item_page_probes.detail_json,
                        item_page_probes.error_message,
                        ROW_NUMBER() OVER (
                            PARTITION BY item_page_probes.listing_id
                            ORDER BY item_page_probes.probed_at DESC, item_page_probes.probe_id DESC
                        ) AS probe_rank
                    FROM item_page_probes
                    {probe_filter}
                )
                WHERE probe_rank = 1
            )
            SELECT
                summary.listing_id,
                summary.observation_count,
                summary.total_sightings,
                summary.first_seen_at,
                summary.last_seen_at,
                summary.average_revisit_hours,
                listings.canonical_url,
                listings.title,
                listings.brand,
                listings.size_label,
                listings.condition_label,
                listings.price_amount_cents,
                listings.price_currency,
                listings.total_price_amount_cents,
                listings.total_price_currency,
                listings.image_url,
                listings.favourite_count,
                listings.view_count,
                listings.user_id,
                listings.user_login,
                listings.user_profile_url,
                listings.created_at_ts,
                roots.title AS root_title,
                listings.primary_catalog_id,
                listings.primary_root_catalog_id,
                primary_catalog.path AS primary_catalog_path,
                primary_catalog.root_title AS primary_catalog_root_title,
                summary.last_observed_run_id,
                latest_primary_scan.run_id AS latest_primary_scan_run_id,
                latest_primary_scan.fetched_at AS latest_primary_scan_at,
                COALESCE(follow_up_miss.follow_up_miss_count, 0) AS follow_up_miss_count,
                follow_up_miss.latest_follow_up_miss_at,
                latest_probe.probe_id AS latest_probe_id,
                latest_probe.probed_at AS latest_probe_probed_at,
                latest_probe.requested_url AS latest_probe_requested_url,
                latest_probe.final_url AS latest_probe_final_url,
                latest_probe.response_status AS latest_probe_response_status,
                latest_probe.probe_outcome AS latest_probe_outcome,
                latest_probe.detail_json AS latest_probe_detail_json,
                latest_probe.error_message AS latest_probe_error_message
            FROM summary
            JOIN listings ON listings.listing_id = summary.listing_id
            LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN latest_primary_scan ON latest_primary_scan.catalog_id = listings.primary_catalog_id
            LEFT JOIN follow_up_miss ON follow_up_miss.listing_id = listings.listing_id
            LEFT JOIN latest_probe ON latest_probe.listing_id = listings.listing_id
            ORDER BY summary.last_seen_at DESC, summary.listing_id DESC
            """,
            params,
        ).fetchall()

        inputs: list[dict[str, object]] = []
        for row in rows:
            enriched = dict(row)
            age_hours = _hours_between(str(enriched["last_seen_at"]), now_dt)
            enriched["last_seen_age_hours"] = round(age_hours, 2)
            enriched["freshness_bucket"] = _freshness_bucket(int(enriched["observation_count"]), age_hours)
            enriched["signal_completeness"] = _signal_completeness(enriched)
            enriched["average_revisit_hours"] = None if enriched["average_revisit_hours"] is None else round(float(enriched["average_revisit_hours"]), 2)
            if enriched.get("latest_probe_id") is None:
                enriched["latest_probe"] = None
            else:
                enriched["latest_probe"] = {
                    "probe_id": enriched.pop("latest_probe_id"),
                    "listing_id": enriched["listing_id"],
                    "probed_at": enriched.pop("latest_probe_probed_at"),
                    "requested_url": enriched.pop("latest_probe_requested_url"),
                    "final_url": enriched.pop("latest_probe_final_url"),
                    "response_status": enriched.pop("latest_probe_response_status"),
                    "probe_outcome": enriched.pop("latest_probe_outcome"),
                    "detail": json.loads(enriched.pop("latest_probe_detail_json") or "{}"),
                    "error_message": enriched.pop("latest_probe_error_message"),
                }
            for transient_field in (
                "latest_probe_id",
                "latest_probe_probed_at",
                "latest_probe_requested_url",
                "latest_probe_final_url",
                "latest_probe_response_status",
                "latest_probe_outcome",
                "latest_probe_detail_json",
                "latest_probe_error_message",
            ):
                enriched.pop(transient_field, None)
            enriched["seen_in_latest_primary_scan"] = (
                enriched.get("latest_primary_scan_run_id") is not None
                and enriched.get("latest_primary_scan_run_id") == enriched.get("last_observed_run_id")
            )
            inputs.append(enriched)
        return inputs

    def overview_snapshot(
        self,
        *,
        now: str | None = None,
        comparison_limit: int = DEFAULT_OVERVIEW_COMPARISON_LIMIT,
        support_threshold: int = DEFAULT_OVERVIEW_SUPPORT_THRESHOLD,
    ) -> dict[str, object]:
        now_dt = _coerce_now(now)
        generated_at = now_dt.replace(microsecond=0).isoformat()
        bounded_limit = max(int(comparison_limit), 1)
        bounded_support_threshold = max(int(support_threshold), 1)
        cte_sql, cte_params = self._overview_state_snapshot_ctes(now_dt=now_dt)

        summary_row = self.connection.execute(
            f"""
            {cte_sql}
            SELECT
                COUNT(*) AS tracked_listings,
                MAX(last_seen_at) AS latest_listing_seen_at,
                MAX(latest_primary_scan_at) AS latest_successful_scan_at,
                SUM(CASE WHEN sold_like = 1 THEN 1 ELSE 0 END) AS sold_like_count,
                SUM(CASE WHEN state_code = 'active' THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN state_code = 'sold_observed' THEN 1 ELSE 0 END) AS sold_observed_count,
                SUM(CASE WHEN state_code = 'sold_probable' THEN 1 ELSE 0 END) AS sold_probable_count,
                SUM(CASE WHEN state_code = 'unavailable_non_conclusive' THEN 1 ELSE 0 END) AS unavailable_non_conclusive_count,
                SUM(CASE WHEN state_code = 'deleted' THEN 1 ELSE 0 END) AS deleted_count,
                SUM(CASE WHEN state_code = 'unknown' THEN 1 ELSE 0 END) AS unknown_count,
                SUM(CASE WHEN basis_kind = 'observed' THEN 1 ELSE 0 END) AS observed_state_count,
                SUM(CASE WHEN basis_kind = 'inferred' THEN 1 ELSE 0 END) AS inferred_state_count,
                SUM(CASE WHEN basis_kind = 'unknown' THEN 1 ELSE 0 END) AS unknown_state_count,
                SUM(CASE WHEN confidence_label = 'high' THEN 1 ELSE 0 END) AS high_confidence_count,
                SUM(CASE WHEN confidence_label = 'medium' THEN 1 ELSE 0 END) AS medium_confidence_count,
                SUM(CASE WHEN confidence_label = 'low' THEN 1 ELSE 0 END) AS low_confidence_count,
                SUM(partial_signal) AS partial_signal_count,
                SUM(thin_signal) AS thin_signal_count,
                SUM(has_estimated_publication) AS estimated_publication_count,
                SUM(CASE WHEN has_estimated_publication = 0 THEN 1 ELSE 0 END) AS missing_estimated_publication_count
            FROM classified
            """,
            cte_params,
        ).fetchone()
        summary_values = dict(summary_row) if summary_row is not None else {}
        coverage = self.coverage_summary()
        runtime = self.runtime_status(limit=5, now=generated_at)
        controller = runtime.get("controller") if isinstance(runtime, dict) else None
        latest_cycle = runtime.get("latest_cycle") if isinstance(runtime, dict) else None
        recent_failures = [] if coverage is None else list(coverage.get("failures") or [])

        comparisons: dict[str, dict[str, object]] = {}
        for spec in (
            {
                "lens": "category",
                "title": "Catégories",
                "value_expression": "CASE WHEN primary_catalog_id IS NOT NULL THEN CAST(primary_catalog_id AS TEXT) ELSE COALESCE(root_title, 'unknown-root') END",
                "label_expression": "COALESCE(category_path, COALESCE(root_title, 'Catégorie inconnue'))",
                "extra_select": ", MAX(primary_catalog_id) AS catalog_id, MAX(root_title) AS root_title",
                "order_by": "support_count DESC, lens_label ASC",
            },
            {
                "lens": "brand",
                "title": "Marques",
                "value_expression": "COALESCE(brand, 'unknown-brand')",
                "label_expression": "COALESCE(brand, 'Marque inconnue')",
                "extra_select": "",
                "order_by": "support_count DESC, lens_label ASC",
            },
            {
                "lens": "price_band",
                "title": "Tranches de prix",
                "value_expression": "price_band_code",
                "label_expression": "price_band_label",
                "extra_select": ", MIN(price_band_sort_order) AS sort_rank",
                "order_by": "support_count DESC, sort_rank ASC, lens_label ASC",
            },
            {
                "lens": "condition",
                "title": "États",
                "value_expression": "COALESCE(condition_label, 'unknown-condition')",
                "label_expression": "COALESCE(condition_label, 'État inconnu')",
                "extra_select": "",
                "order_by": "support_count DESC, lens_label ASC",
            },
            {
                "lens": "sold_state",
                "title": "Statut de vente",
                "value_expression": "state_code",
                "label_expression": "state_label",
                "extra_select": ", MIN(state_sort_order) AS sort_rank",
                "order_by": "support_count DESC, sort_rank ASC, lens_label ASC",
            },
        ):
            comparisons[str(spec["lens"])] = self._overview_comparison_module(
                cte_sql=cte_sql,
                cte_params=cte_params,
                lens=str(spec["lens"]),
                title=str(spec["title"]),
                value_expression=str(spec["value_expression"]),
                label_expression=str(spec["label_expression"]),
                extra_select=str(spec["extra_select"]),
                order_by=str(spec["order_by"]),
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            )

        return {
            "generated_at": generated_at,
            "db_path": str(self.db_path),
            "summary": {
                "inventory": {
                    "tracked_listings": int(summary_values.get("tracked_listings") or 0),
                    "sold_like_count": int(summary_values.get("sold_like_count") or 0),
                    "comparison_support_threshold": bounded_support_threshold,
                    "state_counts": {
                        state_code: int(summary_values.get(f"{state_code}_count") or 0)
                        for state_code in STATE_ORDER
                    },
                },
                "honesty": {
                    "observed_state_count": int(summary_values.get("observed_state_count") or 0),
                    "inferred_state_count": int(summary_values.get("inferred_state_count") or 0),
                    "unknown_state_count": int(summary_values.get("unknown_state_count") or 0),
                    "partial_signal_count": int(summary_values.get("partial_signal_count") or 0),
                    "thin_signal_count": int(summary_values.get("thin_signal_count") or 0),
                    "estimated_publication_count": int(summary_values.get("estimated_publication_count") or 0),
                    "missing_estimated_publication_count": int(summary_values.get("missing_estimated_publication_count") or 0),
                    "confidence_counts": {
                        "high": int(summary_values.get("high_confidence_count") or 0),
                        "medium": int(summary_values.get("medium_confidence_count") or 0),
                        "low": int(summary_values.get("low_confidence_count") or 0),
                    },
                },
                "freshness": {
                    "latest_listing_seen_at": summary_values.get("latest_listing_seen_at"),
                    "latest_successful_scan_at": summary_values.get("latest_successful_scan_at"),
                    "latest_run_id": None if coverage is None else coverage["run"].get("run_id"),
                    "latest_run_started_at": None if coverage is None else coverage["run"].get("started_at"),
                    "latest_run_finished_at": None if coverage is None else coverage["run"].get("finished_at"),
                    "current_runtime_status": runtime.get("status") if isinstance(runtime, dict) else None,
                    "current_runtime_phase": runtime.get("phase") if isinstance(runtime, dict) else None,
                    "current_runtime_updated_at": runtime.get("updated_at") if isinstance(runtime, dict) else None,
                    "current_runtime_next_resume_at": runtime.get("next_resume_at") if isinstance(runtime, dict) else None,
                    "current_runtime_paused_at": runtime.get("paused_at") if isinstance(runtime, dict) else None,
                    "current_runtime_heartbeat_stale": False if controller is None else bool((controller.get("heartbeat") or {}).get("is_stale")),
                    "latest_runtime_cycle_status": None if latest_cycle is None else latest_cycle.get("status"),
                    "latest_runtime_cycle_started_at": None if latest_cycle is None else latest_cycle.get("started_at"),
                    "recent_acquisition_failure_count": len(recent_failures),
                    "recent_acquisition_failures": recent_failures,
                },
            },
            "comparisons": comparisons,
            "coverage": coverage,
            "runtime": runtime,
        }

    def _overview_comparison_module(
        self,
        *,
        cte_sql: str,
        cte_params: list[object],
        lens: str,
        title: str,
        value_expression: str,
        label_expression: str,
        extra_select: str,
        order_by: str,
        limit: int,
        support_threshold: int,
    ) -> dict[str, object]:
        rows = self.connection.execute(
            f"""
            {cte_sql}
            SELECT
                {value_expression} AS lens_value,
                {label_expression} AS lens_label{extra_select},
                COUNT(*) AS support_count,
                ROUND(COUNT(*) * 1.0 / NULLIF(totals.tracked_listings, 0), 3) AS support_share,
                ROUND(AVG(CAST(price_amount_cents AS REAL)), 2) AS average_price_amount_cents,
                SUM(CASE WHEN state_code = 'active' THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN state_code = 'sold_observed' THEN 1 ELSE 0 END) AS sold_observed_count,
                SUM(CASE WHEN state_code = 'sold_probable' THEN 1 ELSE 0 END) AS sold_probable_count,
                SUM(CASE WHEN state_code = 'unavailable_non_conclusive' THEN 1 ELSE 0 END) AS unavailable_non_conclusive_count,
                SUM(CASE WHEN state_code = 'deleted' THEN 1 ELSE 0 END) AS deleted_count,
                SUM(CASE WHEN state_code = 'unknown' THEN 1 ELSE 0 END) AS unknown_count,
                SUM(sold_like) AS sold_like_count,
                ROUND(SUM(sold_like) * 1.0 / COUNT(*), 3) AS sold_like_rate,
                SUM(CASE WHEN basis_kind = 'observed' THEN 1 ELSE 0 END) AS observed_state_count,
                SUM(CASE WHEN basis_kind = 'inferred' THEN 1 ELSE 0 END) AS inferred_state_count,
                SUM(CASE WHEN basis_kind = 'unknown' THEN 1 ELSE 0 END) AS unknown_state_count,
                SUM(partial_signal) AS partial_signal_count,
                SUM(thin_signal) AS thin_signal_count,
                SUM(has_estimated_publication) AS estimated_publication_count,
                SUM(CASE WHEN has_estimated_publication = 0 THEN 1 ELSE 0 END) AS missing_estimated_publication_count
            FROM classified
            CROSS JOIN (SELECT COUNT(*) AS tracked_listings FROM classified) AS totals
            GROUP BY {value_expression}, {label_expression}
            ORDER BY {order_by}
            LIMIT ?
            """,
            [*cte_params, max(int(limit), 1)],
        ).fetchall()

        items: list[dict[str, object]] = []
        for row in rows:
            hydrated = dict(row)
            lens_value = hydrated.get("lens_value")
            support_count = int(hydrated.get("support_count") or 0)
            if lens == "category" and hydrated.get("catalog_id") is not None:
                filters: dict[str, object] = {"catalog_id": int(hydrated["catalog_id"])}
            elif lens == "sold_state":
                filters = {"state": str(lens_value)}
            elif lens == "brand":
                filters = {"brand": str(lens_value)}
            elif lens == "condition":
                filters = {"condition": str(lens_value)}
            elif lens == "price_band":
                filters = {"price_band": str(lens_value)}
            elif hydrated.get("root_title"):
                filters = {"root": str(hydrated["root_title"])}
            else:
                filters = {lens: str(lens_value)}

            items.append(
                {
                    "label": hydrated.get("lens_label"),
                    "value": lens_value,
                    "drilldown": {
                        "lens": lens,
                        "value": lens_value,
                        "filters": filters,
                    },
                    "inventory": {
                        "support_count": support_count,
                        "support_share": float(hydrated.get("support_share") or 0.0),
                        "average_price_amount_cents": None
                        if hydrated.get("average_price_amount_cents") is None
                        else round(float(hydrated["average_price_amount_cents"]), 2),
                        "sold_like_count": int(hydrated.get("sold_like_count") or 0),
                        "sold_like_rate": float(hydrated.get("sold_like_rate") or 0.0),
                        "state_counts": {
                            state_code: int(hydrated.get(f"{state_code}_count") or 0)
                            for state_code in STATE_ORDER
                        },
                    },
                    "honesty": {
                        "low_support": support_count < support_threshold,
                        "support_threshold": support_threshold,
                        "observed_state_count": int(hydrated.get("observed_state_count") or 0),
                        "inferred_state_count": int(hydrated.get("inferred_state_count") or 0),
                        "unknown_state_count": int(hydrated.get("unknown_state_count") or 0),
                        "partial_signal_count": int(hydrated.get("partial_signal_count") or 0),
                        "thin_signal_count": int(hydrated.get("thin_signal_count") or 0),
                        "estimated_publication_count": int(hydrated.get("estimated_publication_count") or 0),
                        "missing_estimated_publication_count": int(hydrated.get("missing_estimated_publication_count") or 0),
                    },
                }
            )

        supported_rows = sum(1 for item in items if not bool(item["honesty"]["low_support"]))
        if not items:
            status = "empty"
            reason = "No tracked listings are available for this comparison lens yet."
        elif supported_rows == 0:
            status = "thin-support"
            reason = f"No lens value reaches the minimum support threshold of {support_threshold} tracked listings."
        else:
            status = "ok"
            reason = None

        return {
            "lens": lens,
            "title": title,
            "support_threshold": support_threshold,
            "status": status,
            "reason": reason,
            "total_rows": len(items),
            "supported_rows": supported_rows,
            "thin_support_rows": len(items) - supported_rows,
            "rows": items,
        }

    def _overview_state_snapshot_ctes(self, *, now_dt: datetime) -> tuple[str, list[object]]:
        generated_at = now_dt.replace(microsecond=0).isoformat()
        cte_sql = f"""
        WITH ordered_observations AS (
            SELECT
                listing_observations.listing_id,
                listing_observations.observed_at,
                listing_observations.sighting_count,
                LAG(listing_observations.observed_at) OVER (
                    PARTITION BY listing_observations.listing_id
                    ORDER BY listing_observations.observed_at
                ) AS previous_observed_at,
                ROW_NUMBER() OVER (
                    PARTITION BY listing_observations.listing_id
                    ORDER BY listing_observations.observed_at DESC, listing_observations.run_id DESC
                ) AS observation_recency_rank,
                listing_observations.run_id
            FROM listing_observations
        ),
        observation_summary AS (
            SELECT
                ordered_observations.listing_id,
                COUNT(*) AS observation_count,
                SUM(ordered_observations.sighting_count) AS total_sightings,
                MIN(ordered_observations.observed_at) AS first_seen_at,
                MAX(ordered_observations.observed_at) AS last_seen_at,
                AVG(CASE
                    WHEN ordered_observations.previous_observed_at IS NULL THEN NULL
                    ELSE (julianday(ordered_observations.observed_at) - julianday(ordered_observations.previous_observed_at)) * 24.0
                END) AS average_revisit_hours,
                MAX(CASE WHEN ordered_observations.observation_recency_rank = 1 THEN ordered_observations.run_id END) AS last_observed_run_id
            FROM ordered_observations
            GROUP BY ordered_observations.listing_id
        ),
        latest_primary_scan AS (
            SELECT catalog_id, run_id, fetched_at
            FROM (
                SELECT
                    catalog_scans.catalog_id,
                    catalog_scans.run_id,
                    catalog_scans.fetched_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY catalog_scans.catalog_id
                        ORDER BY catalog_scans.fetched_at DESC, catalog_scans.run_id DESC
                    ) AS scan_rank
                FROM catalog_scans
                WHERE catalog_scans.success = 1
            )
            WHERE scan_rank = 1
        ),
        follow_up_miss AS (
            SELECT
                observation_summary.listing_id,
                COUNT(DISTINCT scans.run_id) AS follow_up_miss_count,
                MAX(scans.fetched_at) AS latest_follow_up_miss_at
            FROM observation_summary
            JOIN listings ON listings.listing_id = observation_summary.listing_id
            LEFT JOIN catalog_scans AS scans
              ON scans.catalog_id = listings.primary_catalog_id
             AND scans.success = 1
             AND scans.fetched_at > observation_summary.last_seen_at
            LEFT JOIN listing_observations AS observations
              ON observations.listing_id = observation_summary.listing_id
             AND observations.run_id = scans.run_id
            WHERE observations.run_id IS NULL
            GROUP BY observation_summary.listing_id
        ),
        latest_probe AS (
            SELECT
                listing_id,
                probed_at,
                response_status,
                probe_outcome,
                error_message
            FROM (
                SELECT
                    item_page_probes.listing_id,
                    item_page_probes.probed_at,
                    item_page_probes.response_status,
                    item_page_probes.probe_outcome,
                    item_page_probes.error_message,
                    ROW_NUMBER() OVER (
                        PARTITION BY item_page_probes.listing_id
                        ORDER BY item_page_probes.probed_at DESC, item_page_probes.probe_id DESC
                    ) AS probe_rank
                FROM item_page_probes
            )
            WHERE probe_rank = 1
        ),
        snapshot AS (
            SELECT
                observation_summary.listing_id,
                listings.primary_catalog_id,
                listings.primary_root_catalog_id,
                COALESCE(roots.title, 'Unknown') AS root_title,
                COALESCE(primary_catalog.path, COALESCE(roots.title, 'Unknown')) AS category_path,
                listings.title,
                listings.brand,
                listings.size_label,
                listings.condition_label,
                listings.price_amount_cents,
                listings.price_currency,
                listings.total_price_amount_cents,
                listings.total_price_currency,
                listings.image_url,
                listings.created_at_ts,
                observation_summary.observation_count,
                observation_summary.total_sightings,
                observation_summary.first_seen_at,
                observation_summary.last_seen_at,
                ROUND(observation_summary.average_revisit_hours, 2) AS average_revisit_hours,
                observation_summary.last_observed_run_id,
                latest_primary_scan.run_id AS latest_primary_scan_run_id,
                latest_primary_scan.fetched_at AS latest_primary_scan_at,
                COALESCE(follow_up_miss.follow_up_miss_count, 0) AS follow_up_miss_count,
                follow_up_miss.latest_follow_up_miss_at,
                CASE
                    WHEN latest_primary_scan.run_id IS NOT NULL
                     AND latest_primary_scan.run_id = observation_summary.last_observed_run_id
                    THEN 1 ELSE 0
                END AS seen_in_latest_primary_scan,
                latest_probe.probed_at AS latest_probe_at,
                latest_probe.response_status AS latest_probe_response_status,
                latest_probe.probe_outcome AS latest_probe_outcome,
                latest_probe.error_message AS latest_probe_error_message,
                CASE
                    WHEN (julianday(?) - julianday(observation_summary.last_seen_at)) * 24.0 < 0 THEN 0.0
                    ELSE ROUND((julianday(?) - julianday(observation_summary.last_seen_at)) * 24.0, 2)
                END AS last_seen_age_hours,
                (
                    CASE WHEN listings.title IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.brand IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.size_label IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.condition_label IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.price_amount_cents IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.total_price_amount_cents IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN listings.image_url IS NOT NULL THEN 1 ELSE 0 END
                ) AS signal_completeness,
                CASE WHEN listings.created_at_ts IS NULL THEN 0 ELSE 1 END AS has_estimated_publication,
                CASE
                    WHEN listings.price_amount_cents IS NULL THEN 'unknown'
                    WHEN listings.price_amount_cents < 2000 THEN 'under_20_eur'
                    WHEN listings.price_amount_cents < 4000 THEN '20_to_39_eur'
                    ELSE '40_plus_eur'
                END AS price_band_code,
                CASE
                    WHEN listings.price_amount_cents IS NULL THEN 'Prix indisponible'
                    WHEN listings.price_amount_cents < 2000 THEN '< 20 €'
                    WHEN listings.price_amount_cents < 4000 THEN '20–39 €'
                    ELSE '40 € et plus'
                END AS price_band_label,
                CASE
                    WHEN listings.price_amount_cents IS NULL THEN 4
                    WHEN listings.price_amount_cents < 2000 THEN 1
                    WHEN listings.price_amount_cents < 4000 THEN 2
                    ELSE 3
                END AS price_band_sort_order
            FROM observation_summary
            JOIN listings ON listings.listing_id = observation_summary.listing_id
            LEFT JOIN catalogs AS roots ON roots.catalog_id = listings.primary_root_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN latest_primary_scan ON latest_primary_scan.catalog_id = listings.primary_catalog_id
            LEFT JOIN follow_up_miss ON follow_up_miss.listing_id = observation_summary.listing_id
            LEFT JOIN latest_probe ON latest_probe.listing_id = observation_summary.listing_id
        ),
        classified_base AS (
            SELECT
                snapshot.*,
                CASE
                    WHEN observation_count <= 1 THEN 'first-pass-only'
                    WHEN last_seen_age_hours <= {FRESH_FOLLOWUP_HOURS} THEN 'fresh-followup'
                    WHEN last_seen_age_hours <= {STALE_FOLLOWUP_HOURS} THEN 'aging-followup'
                    ELSE 'stale-followup'
                END AS freshness_bucket,
                CASE WHEN signal_completeness < {FULL_SIGNAL_COMPLETENESS} THEN 1 ELSE 0 END AS partial_signal,
                CASE WHEN signal_completeness < {HIGH_SIGNAL_COMPLETENESS} THEN 1 ELSE 0 END AS thin_signal,
                CASE
                    WHEN latest_probe_outcome = 'deleted' THEN 'deleted'
                    WHEN latest_probe_outcome = 'sold' THEN 'sold_observed'
                    WHEN latest_probe_outcome = 'active' THEN 'active'
                    WHEN latest_probe_outcome = 'unavailable' THEN 'unavailable_non_conclusive'
                    WHEN seen_in_latest_primary_scan = 1 THEN 'active'
                    WHEN follow_up_miss_count >= 2 THEN 'sold_probable'
                    WHEN follow_up_miss_count = 1 THEN 'unavailable_non_conclusive'
                    WHEN latest_primary_scan_run_id IS NULL AND last_seen_age_hours <= {ACTIVE_RECENT_WITHOUT_RESCAN_HOURS} THEN 'active'
                    WHEN last_seen_age_hours > {STALE_HISTORY_UNKNOWN_HOURS} THEN 'unknown'
                    ELSE 'unknown'
                END AS state_code,
                CASE
                    WHEN latest_probe_outcome IN ('deleted', 'sold', 'active', 'unavailable') THEN 'observed'
                    WHEN seen_in_latest_primary_scan = 1 THEN 'observed'
                    WHEN follow_up_miss_count >= 1 THEN 'inferred'
                    WHEN latest_primary_scan_run_id IS NULL AND last_seen_age_hours <= {ACTIVE_RECENT_WITHOUT_RESCAN_HOURS} THEN 'inferred'
                    ELSE 'unknown'
                END AS basis_kind,
                ROUND(CASE
                    WHEN latest_probe_outcome = 'deleted' THEN {DELETED_OBSERVED_CONFIDENCE}
                    WHEN latest_probe_outcome = 'sold' THEN {SOLD_OBSERVED_CONFIDENCE}
                    WHEN latest_probe_outcome = 'active' THEN {ACTIVE_PROBE_OBSERVED_CONFIDENCE}
                    WHEN latest_probe_outcome = 'unavailable' THEN {UNAVAILABLE_OBSERVED_CONFIDENCE}
                    WHEN seen_in_latest_primary_scan = 1 THEN {ACTIVE_LATEST_SCAN_OBSERVED_CONFIDENCE}
                    WHEN follow_up_miss_count = 2 THEN {SOLD_PROBABLE_TWO_MISS_CONFIDENCE}
                    WHEN follow_up_miss_count >= 3 THEN {SOLD_PROBABLE_MULTI_MISS_CONFIDENCE}
                    WHEN follow_up_miss_count = 1 THEN {UNAVAILABLE_SINGLE_MISS_INFERRED_CONFIDENCE}
                    WHEN latest_primary_scan_run_id IS NULL AND last_seen_age_hours <= {ACTIVE_RECENT_WITHOUT_RESCAN_HOURS} THEN {ACTIVE_RECENT_NO_RESCAN_INFERRED_CONFIDENCE}
                    WHEN last_seen_age_hours > {STALE_HISTORY_UNKNOWN_HOURS} THEN {UNKNOWN_STALE_CONFIDENCE}
                    ELSE {UNKNOWN_INCONCLUSIVE_CONFIDENCE}
                END, 2) AS confidence_score
            FROM snapshot
        ),
        classified AS (
            SELECT
                classified_base.*,
                CASE
                    WHEN confidence_score >= {HIGH_CONFIDENCE} THEN 'high'
                    WHEN confidence_score >= {MEDIUM_CONFIDENCE} THEN 'medium'
                    ELSE 'low'
                END AS confidence_label,
                CASE state_code
                    WHEN 'active' THEN 'Actif'
                    WHEN 'sold_observed' THEN 'Vendu observé'
                    WHEN 'sold_probable' THEN 'Vendu probable'
                    WHEN 'unavailable_non_conclusive' THEN 'Indisponible'
                    WHEN 'deleted' THEN 'Supprimée'
                    ELSE 'Inconnu'
                END AS state_label,
                CASE state_code
                    WHEN 'active' THEN 1
                    WHEN 'sold_observed' THEN 2
                    WHEN 'sold_probable' THEN 3
                    WHEN 'unavailable_non_conclusive' THEN 4
                    WHEN 'deleted' THEN 5
                    ELSE 6
                END AS state_sort_order,
                CASE WHEN state_code IN ('sold_observed', 'sold_probable') THEN 1 ELSE 0 END AS sold_like
            FROM classified_base
        )
        """
        return cte_sql, [generated_at, generated_at]

    def _hydrate_observation_row(self, row: sqlite3.Row) -> dict[str, object]:
        raw_payload = json.loads(row["raw_card_payload_json"]) if row["raw_card_payload_json"] else {}
        fallback = normalize_card_snapshot(
            raw_card_payload=raw_payload,
            source_url=row["source_url"],
            canonical_url=row["canonical_url"],
            image_url=row["image_url"],
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

    def _hydrate_runtime_cycle_row(self, row: sqlite3.Row) -> dict[str, object]:
        hydrated = dict(row)
        config_json = hydrated.pop("config_json", "{}")
        hydrated["config"] = _deserialize_runtime_config(config_json)
        hydrated["freshness_counts"] = {
            "first-pass-only": int(hydrated.get("first_pass_only") or 0),
            "fresh-followup": int(hydrated.get("fresh_followup") or 0),
            "aging-followup": int(hydrated.get("aging_followup") or 0),
            "stale-followup": int(hydrated.get("stale_followup") or 0),
        }
        return hydrated

    def _hydrate_runtime_controller_row(self, row: sqlite3.Row, *, now_dt: datetime) -> dict[str, object]:
        hydrated = dict(row)
        config_json = hydrated.pop("config_json", "{}")
        hydrated["config"] = _deserialize_runtime_config(config_json)
        updated_at = hydrated.get("updated_at")
        paused_at = hydrated.get("paused_at")
        next_resume_at = hydrated.get("next_resume_at")
        age_seconds = None if updated_at is None else _seconds_between(str(updated_at), now_dt)
        elapsed_pause_seconds = None if paused_at is None else _seconds_between(str(paused_at), now_dt)
        next_resume_in_seconds = None if next_resume_at is None else max(_seconds_until(str(next_resume_at), now_dt), 0.0)
        stale_after_seconds = _runtime_heartbeat_stale_after_seconds(
            status=None if hydrated.get("status") is None else str(hydrated["status"]),
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

    def _runtime_controller_row(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM runtime_controller_state WHERE controller_id = ?",
            (_RUNTIME_CONTROLLER_SINGLETON_ID,),
        ).fetchone()

    def _upsert_runtime_controller_state(
        self,
        *,
        status: str | object = _UNSET,
        phase: str | object = _UNSET,
        mode: str | None | object = _UNSET,
        active_cycle_id: str | None | object = _UNSET,
        latest_cycle_id: str | None | object = _UNSET,
        interval_seconds: float | None | object = _UNSET,
        updated_at: str | None | object = _UNSET,
        paused_at: str | None | object = _UNSET,
        next_resume_at: str | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        last_error_at: str | None | object = _UNSET,
        requested_action: str | object = _UNSET,
        requested_at: str | None | object = _UNSET,
        config: dict[str, object] | object = _UNSET,
    ) -> None:
        existing_row = self._runtime_controller_row()
        if existing_row is None:
            payload: dict[str, object | None] = {
                "controller_id": _RUNTIME_CONTROLLER_SINGLETON_ID,
                "status": "idle",
                "phase": "idle",
                "mode": None,
                "active_cycle_id": None,
                "latest_cycle_id": None,
                "interval_seconds": None,
                "updated_at": None,
                "paused_at": None,
                "next_resume_at": None,
                "last_error": None,
                "last_error_at": None,
                "requested_action": "none",
                "requested_at": None,
                "config": {},
            }
        else:
            payload = dict(existing_row)
            payload["config"] = _deserialize_runtime_config(payload.pop("config_json", "{}"))

        if status is not _UNSET:
            payload["status"] = None if status is None else str(status)
        if phase is not _UNSET:
            payload["phase"] = None if phase is None else str(phase)
        if mode is not _UNSET:
            payload["mode"] = None if mode is None else str(mode)
        if active_cycle_id is not _UNSET:
            payload["active_cycle_id"] = None if active_cycle_id is None else str(active_cycle_id)
        if latest_cycle_id is not _UNSET:
            payload["latest_cycle_id"] = None if latest_cycle_id is None else str(latest_cycle_id)
        if interval_seconds is not _UNSET:
            payload["interval_seconds"] = None if interval_seconds is None else float(interval_seconds)
        if updated_at is _UNSET:
            payload["updated_at"] = _utc_now()
        else:
            payload["updated_at"] = None if updated_at is None else str(updated_at)
        if paused_at is not _UNSET:
            payload["paused_at"] = None if paused_at is None else str(paused_at)
        if next_resume_at is not _UNSET:
            payload["next_resume_at"] = None if next_resume_at is None else str(next_resume_at)
        if last_error is not _UNSET:
            payload["last_error"] = None if last_error is None else str(last_error)
        if last_error_at is not _UNSET:
            payload["last_error_at"] = None if last_error_at is None else str(last_error_at)
        if requested_action is not _UNSET:
            normalized_action = "none" if requested_action in {None, "", "none"} else str(requested_action)
            payload["requested_action"] = normalized_action
            if normalized_action == "none" and requested_at is _UNSET:
                payload["requested_at"] = None
        if requested_at is not _UNSET:
            payload["requested_at"] = None if requested_at is None else str(requested_at)
        if config is not _UNSET:
            payload["config"] = _sanitize_runtime_config(config)
        elif "config" not in payload:
            payload["config"] = {}

        if payload.get("status") is None:
            payload["status"] = "idle"
        if payload.get("phase") is None:
            payload["phase"] = "idle"
        if payload.get("requested_action") is None:
            payload["requested_action"] = "none"
        payload["config"] = _sanitize_runtime_config(payload.get("config") or {})

        self.connection.execute(
            """
            INSERT INTO runtime_controller_state (
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
                config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(controller_id) DO UPDATE SET
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
                config_json = excluded.config_json
            """,
            (
                _RUNTIME_CONTROLLER_SINGLETON_ID,
                payload["status"],
                payload["phase"],
                payload.get("mode"),
                payload.get("active_cycle_id"),
                payload.get("latest_cycle_id"),
                payload.get("interval_seconds"),
                payload.get("updated_at"),
                payload.get("paused_at"),
                payload.get("next_resume_at"),
                payload.get("last_error"),
                payload.get("last_error_at"),
                payload.get("requested_action") or "none",
                payload.get("requested_at"),
                _serialize_runtime_config(payload.get("config") or {}),
            ),
        )

    def _resolve_run(self, run_id: str | None) -> sqlite3.Row | None:
        if run_id is None:
            return self.latest_run()
        return self.connection.execute(
            "SELECT * FROM discovery_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()


def _empty_freshness_bucket_counts(*, root_title: str | None = None) -> dict[str, int | str]:
    bucket_counts: dict[str, int | str] = {
        "tracked_listings": 0,
        "first-pass-only": 0,
        "fresh-followup": 0,
        "aging-followup": 0,
        "stale-followup": 0,
    }
    if root_title is not None:
        bucket_counts["root_title"] = root_title
    return bucket_counts


def _freshness_bucket(observation_count: int, age_hours: float) -> str:
    if observation_count <= 1:
        return "first-pass-only"
    if age_hours <= FRESH_FOLLOWUP_HOURS:
        return "fresh-followup"
    if age_hours <= STALE_FOLLOWUP_HOURS:
        return "aging-followup"
    return "stale-followup"


def _signal_completeness(row: dict[str, object]) -> int:
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


def _clean_query_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _coerce_now(now: str | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return datetime.fromisoformat(now)


def _hours_between(timestamp: str, now: datetime) -> float:
    observed_at = datetime.fromisoformat(timestamp)
    return max((now - observed_at).total_seconds() / 3600.0, 0.0)


def _seconds_between(timestamp: str, now: datetime) -> float:
    observed_at = datetime.fromisoformat(timestamp)
    return max((now - observed_at).total_seconds(), 0.0)


def _seconds_until(timestamp: str, now: datetime) -> float:
    target_at = datetime.fromisoformat(timestamp)
    return (target_at - now).total_seconds()


def _runtime_heartbeat_stale_after_seconds(*, status: str | None, interval_seconds: object) -> float:
    if status in {"running", "scheduled"}:
        return 30.0
    if status == "paused":
        return 120.0
    if interval_seconds is not None:
        try:
            return max(min(float(interval_seconds), 300.0), 60.0)
        except (TypeError, ValueError):
            pass
    return 300.0


def _controller_status_from_runtime_cycle_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized == "running":
        return "running"
    if normalized == "failed":
        return "failed"
    return "idle"


def _controller_phase_from_runtime_state(status: str, phase: str) -> str:
    if status == "idle":
        return "idle"
    return phase


def _sanitize_runtime_config(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _sanitize_runtime_config(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_runtime_config(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_URL_USERINFO_RE.sub(r"\1***@", value)
    return value


def _serialize_runtime_config(config: object) -> str:
    return json.dumps(_sanitize_runtime_config(config), ensure_ascii=False, sort_keys=True)


def _deserialize_runtime_config(config_json: object) -> dict[str, object]:
    if not config_json:
        return {}
    try:
        loaded = json.loads(str(config_json))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
