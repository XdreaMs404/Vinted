from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import (
    CatalogNode,
    CoverageCounters,
    DiscoveryRun,
    ListingIdentity,
    ListingObservation,
    RawEvidenceFragment,
    ScanCoverage,
    utc_now,
)
from .db import bootstrap_sqlite, connect_sqlite, list_tables


def _serialize_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _deserialize_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _serialize_bool(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _deserialize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class Repository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.connection = connect_sqlite(self.db_path)
        bootstrap_sqlite(self.connection)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Repository:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def list_table_names(self) -> list[str]:
        return list_tables(self.connection)

    def create_discovery_run(self, run: DiscoveryRun) -> DiscoveryRun:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO discovery_runs (
                    run_id,
                    status,
                    requested_roots_json,
                    max_pages_per_catalog,
                    item_details_mode,
                    started_at,
                    completed_at,
                    error_message,
                    observed_at,
                    extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.status,
                    json.dumps(list(run.requested_roots)),
                    run.max_pages_per_catalog,
                    run.item_details_mode,
                    _serialize_datetime(run.started_at),
                    _serialize_datetime(run.completed_at) if run.completed_at else None,
                    run.error_message,
                    _serialize_datetime(run.observed_at),
                    run.extractor_version,
                ),
            )
        return run

    def finish_discovery_run(
        self,
        run_id: str,
        *,
        status: str,
        completed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        finished_at = completed_at or utc_now()
        with self.connection:
            self.connection.execute(
                """
                UPDATE discovery_runs
                SET status = ?, completed_at = ?, error_message = ?
                WHERE run_id = ?
                """,
                (status, _serialize_datetime(finished_at), error_message, run_id),
            )

    def get_discovery_run(self, run_id: str) -> DiscoveryRun | None:
        row = self.connection.execute(
            "SELECT * FROM discovery_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return DiscoveryRun(
            run_id=row["run_id"],
            requested_roots=tuple(json.loads(row["requested_roots_json"])),
            status=row["status"],
            max_pages_per_catalog=row["max_pages_per_catalog"],
            item_details_mode=row["item_details_mode"],
            started_at=_deserialize_datetime(row["started_at"]),
            completed_at=(
                _deserialize_datetime(row["completed_at"]) if row["completed_at"] else None
            ),
            error_message=row["error_message"],
            observed_at=_deserialize_datetime(row["observed_at"]),
            extractor_version=row["extractor_version"],
        )

    def upsert_catalog_node(self, node: CatalogNode) -> CatalogNode:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO catalog_nodes (
                    catalog_id,
                    parent_catalog_id,
                    root_catalog_id,
                    slug,
                    title,
                    path,
                    source_url,
                    is_leaf,
                    observed_at,
                    extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(catalog_id) DO UPDATE SET
                    parent_catalog_id = COALESCE(
                        excluded.parent_catalog_id,
                        catalog_nodes.parent_catalog_id
                    ),
                    root_catalog_id = excluded.root_catalog_id,
                    slug = COALESCE(excluded.slug, catalog_nodes.slug),
                    title = COALESCE(excluded.title, catalog_nodes.title),
                    path = COALESCE(excluded.path, catalog_nodes.path),
                    source_url = COALESCE(excluded.source_url, catalog_nodes.source_url),
                    is_leaf = COALESCE(excluded.is_leaf, catalog_nodes.is_leaf),
                    observed_at = excluded.observed_at,
                    extractor_version = excluded.extractor_version
                """,
                (
                    node.catalog_id,
                    node.parent_catalog_id,
                    node.root_catalog_id,
                    node.slug,
                    node.title,
                    node.path,
                    node.source_url,
                    _serialize_bool(node.is_leaf),
                    _serialize_datetime(node.observed_at),
                    node.extractor_version,
                ),
            )
        return node

    def get_catalog_node(self, catalog_id: int) -> CatalogNode | None:
        row = self.connection.execute(
            "SELECT * FROM catalog_nodes WHERE catalog_id = ?",
            (catalog_id,),
        ).fetchone()
        if row is None:
            return None
        return CatalogNode(
            catalog_id=row["catalog_id"],
            parent_catalog_id=row["parent_catalog_id"],
            root_catalog_id=row["root_catalog_id"],
            slug=row["slug"],
            title=row["title"],
            path=row["path"],
            source_url=row["source_url"],
            is_leaf=_deserialize_bool(row["is_leaf"]),
            observed_at=_deserialize_datetime(row["observed_at"]),
            extractor_version=row["extractor_version"],
        )

    def upsert_listing_identity(self, identity: ListingIdentity) -> ListingIdentity:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO listing_identities (
                    listing_id,
                    source_url,
                    seller_id,
                    seller_login,
                    first_observed_at,
                    last_observed_at,
                    first_extractor_version,
                    last_extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    source_url = COALESCE(excluded.source_url, listing_identities.source_url),
                    seller_id = COALESCE(excluded.seller_id, listing_identities.seller_id),
                    seller_login = COALESCE(excluded.seller_login, listing_identities.seller_login),
                    first_observed_at = CASE
                        WHEN excluded.first_observed_at < listing_identities.first_observed_at
                            THEN excluded.first_observed_at
                        ELSE listing_identities.first_observed_at
                    END,
                    first_extractor_version = CASE
                        WHEN excluded.first_observed_at < listing_identities.first_observed_at
                            THEN excluded.first_extractor_version
                        ELSE listing_identities.first_extractor_version
                    END,
                    last_observed_at = CASE
                        WHEN excluded.last_observed_at > listing_identities.last_observed_at
                            THEN excluded.last_observed_at
                        ELSE listing_identities.last_observed_at
                    END,
                    last_extractor_version = CASE
                        WHEN excluded.last_observed_at > listing_identities.last_observed_at
                            THEN excluded.last_extractor_version
                        ELSE listing_identities.last_extractor_version
                    END
                """,
                (
                    identity.listing_id,
                    identity.source_url,
                    identity.seller_id,
                    identity.seller_login,
                    _serialize_datetime(identity.first_observed_at),
                    _serialize_datetime(identity.last_observed_at),
                    identity.first_extractor_version,
                    identity.last_extractor_version,
                ),
            )
        return self.get_listing_identity(identity.listing_id) or identity

    def get_listing_identity(self, listing_id: str) -> ListingIdentity | None:
        row = self.connection.execute(
            "SELECT * FROM listing_identities WHERE listing_id = ?",
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        return ListingIdentity(
            listing_id=row["listing_id"],
            source_url=row["source_url"],
            seller_id=row["seller_id"],
            seller_login=row["seller_login"],
            first_observed_at=_deserialize_datetime(row["first_observed_at"]),
            last_observed_at=_deserialize_datetime(row["last_observed_at"]),
            first_extractor_version=row["first_extractor_version"],
            last_extractor_version=row["last_extractor_version"],
        )

    def append_listing_observation(self, observation: ListingObservation) -> ListingObservation:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO listing_observations (
                    run_id,
                    listing_id,
                    catalog_id,
                    catalog_page,
                    observed_rank,
                    title,
                    brand,
                    size_label,
                    price_amount,
                    currency_code,
                    status_hint,
                    seller_login,
                    seller_country_code,
                    favourite_count,
                    view_count,
                    image_url,
                    source_url,
                    observed_at,
                    extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.run_id,
                    observation.listing_id,
                    observation.catalog_id,
                    observation.catalog_page,
                    observation.observed_rank,
                    observation.title,
                    observation.brand,
                    observation.size_label,
                    observation.price_amount,
                    observation.currency_code,
                    observation.status_hint,
                    observation.seller_login,
                    observation.seller_country_code,
                    observation.favourite_count,
                    observation.view_count,
                    observation.image_url,
                    observation.source_url,
                    _serialize_datetime(observation.observed_at),
                    observation.extractor_version,
                ),
            )
        return replace(observation, observation_id=int(cursor.lastrowid))

    def get_listing_observations(self, listing_id: str | None = None) -> list[ListingObservation]:
        query = "SELECT * FROM listing_observations"
        params: tuple[Any, ...] = ()
        if listing_id is not None:
            query += " WHERE listing_id = ?"
            params = (listing_id,)
        query += " ORDER BY observed_at, observation_id"
        rows = self.connection.execute(query, params).fetchall()
        return [
            ListingObservation(
                observation_id=row["observation_id"],
                run_id=row["run_id"],
                listing_id=row["listing_id"],
                catalog_id=row["catalog_id"],
                catalog_page=row["catalog_page"],
                observed_rank=row["observed_rank"],
                title=row["title"],
                brand=row["brand"],
                size_label=row["size_label"],
                price_amount=row["price_amount"],
                currency_code=row["currency_code"],
                status_hint=row["status_hint"],
                seller_login=row["seller_login"],
                seller_country_code=row["seller_country_code"],
                favourite_count=row["favourite_count"],
                view_count=row["view_count"],
                image_url=row["image_url"],
                source_url=row["source_url"],
                observed_at=_deserialize_datetime(row["observed_at"]),
                extractor_version=row["extractor_version"],
            )
            for row in rows
        ]

    def record_raw_evidence(self, fragment: RawEvidenceFragment) -> RawEvidenceFragment:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO raw_evidence_fragments (
                    run_id,
                    listing_id,
                    catalog_id,
                    fragment_kind,
                    fragment_key,
                    source_url,
                    content_type,
                    body,
                    observed_at,
                    extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fragment.run_id,
                    fragment.listing_id,
                    fragment.catalog_id,
                    fragment.fragment_kind,
                    fragment.fragment_key,
                    fragment.source_url,
                    fragment.content_type,
                    fragment.body,
                    _serialize_datetime(fragment.observed_at),
                    fragment.extractor_version,
                ),
            )
        return replace(fragment, fragment_id=int(cursor.lastrowid))

    def get_raw_evidence_fragments(self, run_id: str | None = None) -> list[RawEvidenceFragment]:
        query = "SELECT * FROM raw_evidence_fragments"
        params: tuple[Any, ...] = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY observed_at, fragment_id"
        rows = self.connection.execute(query, params).fetchall()
        return [
            RawEvidenceFragment(
                fragment_id=row["fragment_id"],
                run_id=row["run_id"],
                listing_id=row["listing_id"],
                catalog_id=row["catalog_id"],
                fragment_kind=row["fragment_kind"],
                fragment_key=row["fragment_key"],
                source_url=row["source_url"],
                content_type=row["content_type"],
                body=row["body"],
                observed_at=_deserialize_datetime(row["observed_at"]),
                extractor_version=row["extractor_version"],
            )
            for row in rows
        ]

    def record_scan_coverage(self, coverage: ScanCoverage) -> ScanCoverage:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO scan_coverage (
                    run_id,
                    catalog_id,
                    root_catalog_id,
                    page_number,
                    stage,
                    pages_scanned,
                    listing_stubs_seen,
                    unique_listings,
                    duplicate_listings,
                    errors,
                    stop_reason,
                    error_message,
                    observed_at,
                    extractor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coverage.run_id,
                    coverage.catalog_id,
                    coverage.root_catalog_id,
                    coverage.page_number,
                    coverage.stage,
                    coverage.counters.pages_scanned,
                    coverage.counters.listing_stubs_seen,
                    coverage.counters.unique_listings,
                    coverage.counters.duplicate_listings,
                    coverage.counters.errors,
                    coverage.stop_reason,
                    coverage.error_message,
                    _serialize_datetime(coverage.observed_at),
                    coverage.extractor_version,
                ),
            )
        return replace(coverage, coverage_id=int(cursor.lastrowid))

    def get_scan_coverage(self, run_id: str | None = None) -> list[ScanCoverage]:
        query = "SELECT * FROM scan_coverage"
        params: tuple[Any, ...] = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY observed_at, coverage_id"
        rows = self.connection.execute(query, params).fetchall()
        return [
            ScanCoverage(
                coverage_id=row["coverage_id"],
                run_id=row["run_id"],
                catalog_id=row["catalog_id"],
                root_catalog_id=row["root_catalog_id"],
                page_number=row["page_number"],
                stage=row["stage"],
                counters=CoverageCounters(
                    pages_scanned=row["pages_scanned"],
                    listing_stubs_seen=row["listing_stubs_seen"],
                    unique_listings=row["unique_listings"],
                    duplicate_listings=row["duplicate_listings"],
                    errors=row["errors"],
                ),
                stop_reason=row["stop_reason"],
                error_message=row["error_message"],
                observed_at=_deserialize_datetime(row["observed_at"]),
                extractor_version=row["extractor_version"],
            )
            for row in rows
        ]
