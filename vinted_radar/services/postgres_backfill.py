from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinted_radar.platform.config import PlatformConfig, load_platform_config, redact_url_credentials
from vinted_radar.platform.postgres_repository import PostgresMutableTruthRepository
from vinted_radar.repository import FULL_SIGNAL_COMPLETENESS, HIGH_SIGNAL_COMPLETENESS, RadarRepository


@dataclass(frozen=True, slots=True)
class PostgresBackfillReport:
    sqlite_db_path: str
    postgres_dsn: str
    reference_now: str
    discovery_runs: int
    catalogs: int
    listing_identities: int
    listing_presence_summaries: int
    listing_current_states: int
    runtime_cycles: int
    runtime_controller_rows: int

    def as_dict(self) -> dict[str, object]:
        return {
            "sqlite_db_path": self.sqlite_db_path,
            "postgres_dsn": redact_url_credentials(self.postgres_dsn),
            "reference_now": self.reference_now,
            "discovery_runs": self.discovery_runs,
            "catalogs": self.catalogs,
            "listing_identities": self.listing_identities,
            "listing_presence_summaries": self.listing_presence_summaries,
            "listing_current_states": self.listing_current_states,
            "runtime_cycles": self.runtime_cycles,
            "runtime_controller_rows": self.runtime_controller_rows,
        }


class PostgresBackfillService:
    def __init__(
        self,
        sqlite_db_path: str | Path,
        *,
        config: PlatformConfig | None = None,
        connection: object | None = None,
        repository: PostgresMutableTruthRepository | None = None,
        reference_now: str | None = None,
    ) -> None:
        self.sqlite_db_path = Path(sqlite_db_path)
        self.config = load_platform_config() if config is None else config
        self.reference_now = reference_now
        self._owned_connection = connection is None and repository is None
        if repository is not None:
            self.target = repository
        else:
            resolved_connection = _connect_postgres(self.config.postgres.dsn) if connection is None else connection
            self.target = PostgresMutableTruthRepository(resolved_connection)

    def close(self) -> None:
        if self._owned_connection:
            self.target.close()

    def run(self, *, sync_runtime_control: bool = True) -> PostgresBackfillReport:
        reference_now = self.reference_now or _utc_now()
        with RadarRepository(self.sqlite_db_path) as source:
            discovery_runs = self._backfill_discovery_runs(source)
            catalogs = self._backfill_catalogs(source)
            listing_rows = self._backfill_listing_truth(source, reference_now=reference_now)
            runtime_cycles = 0
            runtime_controller_rows = 0
            if sync_runtime_control:
                runtime_cycles = self._backfill_runtime_cycles(source)
                runtime_controller_rows = self._backfill_runtime_controller(source, reference_now=reference_now)

        return PostgresBackfillReport(
            sqlite_db_path=str(self.sqlite_db_path),
            postgres_dsn=self.config.postgres.dsn,
            reference_now=reference_now,
            discovery_runs=discovery_runs,
            catalogs=catalogs,
            listing_identities=listing_rows,
            listing_presence_summaries=listing_rows,
            listing_current_states=listing_rows,
            runtime_cycles=runtime_cycles,
            runtime_controller_rows=runtime_controller_rows,
        )

    def _backfill_discovery_runs(self, source: RadarRepository) -> int:
        rows = [
            dict(row)
            for row in source.connection.execute(
                "SELECT * FROM discovery_runs ORDER BY started_at ASC, run_id ASC"
            ).fetchall()
        ]
        for row in rows:
            event_id = _backfill_event_id("discovery-run", row["run_id"], row["started_at"], row.get("finished_at"))
            self.target._upsert_discovery_run(
                {
                    "run_id": row["run_id"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "status": row["status"],
                    "root_scope": row["root_scope"],
                    "page_limit": int(row["page_limit"]),
                    "max_leaf_categories": row["max_leaf_categories"],
                    "request_delay_seconds": float(row["request_delay_seconds"]),
                    "total_seed_catalogs": int(row["total_seed_catalogs"]),
                    "total_leaf_catalogs": int(row["total_leaf_catalogs"]),
                    "scanned_leaf_catalogs": int(row["scanned_leaf_catalogs"]),
                    "successful_scans": int(row["successful_scans"]),
                    "failed_scans": int(row["failed_scans"]),
                    "raw_listing_hits": int(row["raw_listing_hits"]),
                    "unique_listing_hits": int(row["unique_listing_hits"]),
                    "last_error": row["last_error"],
                    "last_event_id": event_id,
                    "last_manifest_id": None,
                    "projected_at": row["finished_at"] or row["started_at"],
                }
            )
        return len(rows)

    def _backfill_catalogs(self, source: RadarRepository) -> int:
        latest_runs = {
            int(row["catalog_id"]): row["run_id"]
            for row in source.connection.execute(
                """
                WITH ranked AS (
                    SELECT
                        catalog_id,
                        run_id,
                        fetched_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY catalog_id
                            ORDER BY fetched_at DESC, run_id DESC
                        ) AS ranked_row
                    FROM catalog_scans
                )
                SELECT catalog_id, run_id
                FROM ranked
                WHERE ranked_row = 1
                """
            ).fetchall()
        }
        rows = [
            dict(row)
            for row in source.connection.execute(
                "SELECT * FROM catalogs ORDER BY depth ASC, root_title ASC, order_index ASC, catalog_id ASC"
            ).fetchall()
        ]
        for row in rows:
            catalog_id = int(row["catalog_id"])
            last_run_id = latest_runs.get(catalog_id)
            event_id = _backfill_event_id("catalog", catalog_id, row["synced_at"], last_run_id)
            self.target._upsert_catalog(
                {
                    "catalog_id": catalog_id,
                    "root_catalog_id": int(row["root_catalog_id"]),
                    "root_title": row["root_title"],
                    "parent_catalog_id": row["parent_catalog_id"],
                    "title": row["title"],
                    "code": row["code"],
                    "url": row["url"],
                    "path": row["path"],
                    "depth": int(row["depth"]),
                    "is_leaf": bool(row["is_leaf"]),
                    "allow_browsing_subcategories": bool(row["allow_browsing_subcategories"]),
                    "order_index": row["order_index"],
                    "synced_at": row["synced_at"],
                    "last_run_id": last_run_id,
                    "last_event_id": event_id,
                    "last_manifest_id": None,
                    "projected_at": row["synced_at"],
                }
            )
        return len(rows)

    def _backfill_listing_truth(self, source: RadarRepository, *, reference_now: str) -> int:
        listings_by_id = {
            int(row["listing_id"]): dict(row)
            for row in source.connection.execute("SELECT * FROM listings ORDER BY listing_id ASC").fetchall()
        }
        run_ids = {
            int(row["listing_id"]): {
                "first_seen_run_id": row["first_seen_run_id"],
                "last_seen_run_id": row["last_seen_run_id"],
            }
            for row in source.connection.execute(
                """
                WITH ranked AS (
                    SELECT
                        listing_id,
                        run_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY listing_id
                            ORDER BY observed_at ASC, run_id ASC
                        ) AS first_rank,
                        ROW_NUMBER() OVER (
                            PARTITION BY listing_id
                            ORDER BY observed_at DESC, run_id DESC
                        ) AS last_rank
                    FROM listing_observations
                )
                SELECT
                    listing_id,
                    MAX(CASE WHEN first_rank = 1 THEN run_id END) AS first_seen_run_id,
                    MAX(CASE WHEN last_rank = 1 THEN run_id END) AS last_seen_run_id
                FROM ranked
                GROUP BY listing_id
                """
            ).fetchall()
        }
        inputs = source.listing_state_inputs(now=reference_now)
        for item in inputs:
            listing_id = int(item["listing_id"])
            listing_row = listings_by_id.get(listing_id, {})
            run_id_row = run_ids.get(listing_id, {})
            event_id = _backfill_event_id("listing", listing_id, item["last_seen_at"], reference_now)
            first_seen_run_id = _optional_str(run_id_row.get("first_seen_run_id")) or _optional_str(item.get("last_observed_run_id")) or _optional_str(listing_row.get("last_seen_run_id")) or "backfill"
            last_seen_run_id = _optional_str(run_id_row.get("last_seen_run_id")) or _optional_str(item.get("last_observed_run_id")) or _optional_str(listing_row.get("last_seen_run_id")) or first_seen_run_id
            self.target._upsert_listing_identity(
                {
                    "listing_id": listing_id,
                    "canonical_url": item["canonical_url"],
                    "source_url": listing_row.get("source_url") or item["canonical_url"],
                    "title": item.get("title"),
                    "brand": item.get("brand"),
                    "size_label": item.get("size_label"),
                    "condition_label": item.get("condition_label"),
                    "price_amount_cents": item.get("price_amount_cents"),
                    "price_currency": item.get("price_currency"),
                    "total_price_amount_cents": item.get("total_price_amount_cents"),
                    "total_price_currency": item.get("total_price_currency"),
                    "image_url": item.get("image_url"),
                    "favourite_count": item.get("favourite_count"),
                    "view_count": item.get("view_count"),
                    "user_id": item.get("user_id"),
                    "user_login": item.get("user_login"),
                    "user_profile_url": item.get("user_profile_url"),
                    "created_at_ts": item.get("created_at_ts"),
                    "primary_catalog_id": item.get("primary_catalog_id"),
                    "primary_root_catalog_id": item.get("primary_root_catalog_id"),
                    "first_seen_at": item["first_seen_at"],
                    "last_seen_at": item["last_seen_at"],
                    "first_seen_run_id": first_seen_run_id,
                    "last_seen_run_id": last_seen_run_id,
                    "last_event_id": event_id,
                    "last_manifest_id": None,
                    "projected_at": reference_now,
                }
            )

            price_band_code, price_band_label, price_band_sort_order = _price_band(item.get("price_amount_cents"))
            signal_completeness = int(item.get("signal_completeness") or 0)
            self.target._upsert_listing_presence_summary(
                {
                    "listing_id": listing_id,
                    "observation_count": int(item.get("observation_count") or 0),
                    "total_sightings": int(item.get("total_sightings") or 0),
                    "first_seen_at": item["first_seen_at"],
                    "last_seen_at": item["last_seen_at"],
                    "average_revisit_hours": item.get("average_revisit_hours"),
                    "last_observed_run_id": item.get("last_observed_run_id"),
                    "freshness_bucket": item.get("freshness_bucket") or "first-pass-only",
                    "signal_completeness": signal_completeness,
                    "partial_signal": signal_completeness < FULL_SIGNAL_COMPLETENESS,
                    "thin_signal": signal_completeness < HIGH_SIGNAL_COMPLETENESS,
                    "has_estimated_publication": item.get("created_at_ts") is not None,
                    "price_band_code": price_band_code,
                    "price_band_label": price_band_label,
                    "price_band_sort_order": price_band_sort_order,
                    "last_event_id": event_id,
                    "last_manifest_id": None,
                    "projected_at": reference_now,
                }
            )

            latest_probe = dict(item.get("latest_probe") or {})
            latest_primary_scan_run_id = _optional_str(item.get("latest_primary_scan_run_id"))
            last_observed_run_id = _optional_str(item.get("last_observed_run_id"))
            current_payload = self.target._default_listing_current_state(listing_id)
            current_payload.update(
                {
                    "listing_id": listing_id,
                    "seen_in_latest_primary_scan": latest_primary_scan_run_id is not None and latest_primary_scan_run_id == last_observed_run_id,
                    "latest_primary_scan_run_id": latest_primary_scan_run_id,
                    "latest_primary_scan_at": item.get("latest_primary_scan_at"),
                    "follow_up_miss_count": int(item.get("follow_up_miss_count") or 0),
                    "latest_follow_up_miss_at": item.get("latest_follow_up_miss_at"),
                    "latest_probe_at": latest_probe.get("probed_at"),
                    "latest_probe_response_status": latest_probe.get("response_status"),
                    "latest_probe_outcome": latest_probe.get("probe_outcome"),
                    "latest_probe_error_message": latest_probe.get("error_message"),
                    "last_event_id": event_id,
                    "last_manifest_id": None,
                    "projected_at": reference_now,
                }
            )
            self.target._upsert_listing_current_state_row(current_payload)
            self.target._refresh_projected_listing(
                listing_id,
                now=reference_now,
                source_event_id=event_id,
                source_manifest_id=None,
            )
        return len(inputs)

    def _backfill_runtime_cycles(self, source: RadarRepository) -> int:
        cycle_ids = [
            str(row["cycle_id"])
            for row in source.connection.execute(
                "SELECT cycle_id FROM runtime_cycles ORDER BY started_at ASC, cycle_id ASC"
            ).fetchall()
        ]
        for cycle_id in cycle_ids:
            cycle = source.runtime_cycle(cycle_id)
            if cycle is None:
                continue
            self.target.project_runtime_cycle_snapshot(
                cycle=cycle,
                event_id=_backfill_event_id("runtime-cycle", cycle_id, cycle.get("started_at"), cycle.get("finished_at")),
            )
        return len(cycle_ids)

    def _backfill_runtime_controller(self, source: RadarRepository, *, reference_now: str) -> int:
        controller = source.runtime_controller_state(now=reference_now)
        if controller is None:
            return 0
        self.target.project_runtime_controller_snapshot(
            controller=controller,
            event_id=_backfill_event_id(
                "runtime-controller",
                controller.get("status"),
                controller.get("phase"),
                controller.get("updated_at"),
            ),
        )
        return 1


def backfill_postgres_mutable_truth(
    sqlite_db_path: str | Path,
    *,
    config: PlatformConfig | None = None,
    connection: object | None = None,
    repository: PostgresMutableTruthRepository | None = None,
    reference_now: str | None = None,
    sync_runtime_control: bool = True,
) -> PostgresBackfillReport:
    service = PostgresBackfillService(
        sqlite_db_path,
        config=config,
        connection=connection,
        repository=repository,
        reference_now=reference_now,
    )
    try:
        return service.run(sync_runtime_control=sync_runtime_control)
    finally:
        service.close()


def _price_band(price_amount_cents: object) -> tuple[str, str, int]:
    price = _optional_int(price_amount_cents)
    if price is None:
        return "unknown", "Prix indisponible", 4
    if price < 2000:
        return "under_20_eur", "< 20 €", 1
    if price < 4000:
        return "20_to_39_eur", "20–39 €", 2
    return "40_plus_eur", "40 € et plus", 3


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _backfill_event_id(*parts: object) -> str:
    return "sqlite-backfill:" + ":".join(str(part) for part in parts if part is not None)


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _connect_postgres(dsn: str):
    import psycopg

    return psycopg.connect(dsn)


__all__ = [
    "PostgresBackfillReport",
    "PostgresBackfillService",
    "backfill_postgres_mutable_truth",
]
