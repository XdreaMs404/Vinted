from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta

from vinted_radar.models import (
    CatalogNode,
    CoverageCounters,
    DiscoveryRun,
    ListingIdentity,
    ListingObservation,
    RawEvidenceFragment,
    ScanCoverage,
)
from vinted_radar.storage.db import REQUIRED_TABLES
from vinted_radar.storage.repository import Repository


def test_bootstrap_creates_required_tables(repository: Repository, db_path) -> None:
    assert REQUIRED_TABLES.issubset(set(repository.list_table_names()))

    with sqlite3.connect(db_path) as connection:
        observation_columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(listing_observations)")
        }
        evidence_columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(raw_evidence_fragments)")
        }

    assert observation_columns["title"][3] == 0
    assert observation_columns["brand"][3] == 0
    assert observation_columns["price_amount"][3] == 0
    assert observation_columns["currency_code"][3] == 0
    assert evidence_columns["body"][3] == 1
    assert evidence_columns["extractor_version"][3] == 1


def test_listing_observations_are_append_only(repository: Repository, observed_at) -> None:
    repository.create_discovery_run(
        DiscoveryRun(
            run_id="run-append-only",
            requested_roots=(5,),
            started_at=observed_at,
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    repository.upsert_catalog_node(
        CatalogNode(
            catalog_id=5,
            root_catalog_id=5,
            title="Men",
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    repository.upsert_listing_identity(
        ListingIdentity(
            listing_id="12345",
            source_url="https://www.vinted.com/items/12345",
            first_observed_at=observed_at,
            last_observed_at=observed_at,
            first_extractor_version="test-suite-v1",
            last_extractor_version="test-suite-v1",
        )
    )

    first = repository.append_listing_observation(
        ListingObservation(
            run_id="run-append-only",
            listing_id="12345",
            catalog_id=5,
            catalog_page=1,
            observed_rank=1,
            title="Vintage jacket",
            price_amount=24.0,
            currency_code="EUR",
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    second = repository.append_listing_observation(
        replace(
            first,
            observation_id=None,
            title="Vintage jacket - refreshed",
            observed_rank=3,
            observed_at=observed_at + timedelta(minutes=15),
        )
    )

    observations = repository.get_listing_observations("12345")

    assert len(observations) == 2
    assert first.observation_id != second.observation_id
    assert [item.title for item in observations] == [
        "Vintage jacket",
        "Vintage jacket - refreshed",
    ]
    assert [item.observed_rank for item in observations] == [1, 3]


def test_nullable_public_fields_round_trip(repository: Repository, observed_at) -> None:
    repository.create_discovery_run(
        DiscoveryRun(
            run_id="run-nullable",
            requested_roots=(1904,),
            started_at=observed_at,
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    stored_identity = repository.upsert_listing_identity(
        ListingIdentity(
            listing_id="nullable-listing",
            source_url=None,
            seller_id=None,
            seller_login=None,
            first_observed_at=observed_at,
            last_observed_at=observed_at,
            first_extractor_version="test-suite-v1",
            last_extractor_version="test-suite-v1",
        )
    )
    repository.append_listing_observation(
        ListingObservation(
            run_id="run-nullable",
            listing_id="nullable-listing",
            catalog_id=None,
            catalog_page=None,
            observed_rank=None,
            title=None,
            brand=None,
            size_label=None,
            price_amount=None,
            currency_code=None,
            status_hint=None,
            seller_login=None,
            seller_country_code=None,
            favourite_count=None,
            view_count=None,
            image_url=None,
            source_url=None,
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )

    observation = repository.get_listing_observations("nullable-listing")[0]

    assert stored_identity.source_url is None
    assert stored_identity.seller_id is None
    assert stored_identity.seller_login is None
    assert observation.catalog_id is None
    assert observation.title is None
    assert observation.brand is None
    assert observation.currency_code is None
    assert observation.source_url is None


def test_raw_evidence_and_coverage_are_persisted(repository: Repository, observed_at) -> None:
    repository.create_discovery_run(
        DiscoveryRun(
            run_id="run-observability",
            requested_roots=(5, 1904),
            item_details_mode="sample",
            started_at=observed_at,
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    repository.upsert_catalog_node(
        CatalogNode(
            catalog_id=1904,
            root_catalog_id=1904,
            title="Women",
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )

    stored_coverage = repository.record_scan_coverage(
        ScanCoverage(
            run_id="run-observability",
            catalog_id=1904,
            root_catalog_id=1904,
            page_number=1,
            counters=CoverageCounters(
                pages_scanned=1,
                listing_stubs_seen=24,
                unique_listings=20,
                duplicate_listings=4,
                errors=0,
            ),
            stop_reason="page_limit",
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    stored_fragment = repository.record_raw_evidence(
        RawEvidenceFragment(
            run_id="run-observability",
            catalog_id=1904,
            fragment_kind="catalog_items",
            fragment_key="catalog-1904-page-1",
            source_url="https://www.vinted.com/catalog/1904",
            body='{"items": [{"id": "12345"}]}',
            observed_at=observed_at,
            extractor_version="test-suite-v1",
        )
    )
    repository.finish_discovery_run(
        "run-observability",
        status="completed",
        completed_at=observed_at + timedelta(minutes=2),
    )

    run = repository.get_discovery_run("run-observability")
    coverage_rows = repository.get_scan_coverage("run-observability")
    evidence_rows = repository.get_raw_evidence_fragments("run-observability")

    assert run is not None
    assert run.status == "completed"
    assert run.completed_at == observed_at + timedelta(minutes=2)
    assert stored_coverage.coverage_id is not None
    assert coverage_rows[0].counters.unique_listings == 20
    assert coverage_rows[0].stop_reason == "page_limit"
    assert coverage_rows[0].extractor_version == "test-suite-v1"
    assert stored_fragment.fragment_id is not None
    assert evidence_rows[0].body == '{"items": [{"id": "12345"}]}'
    assert evidence_rows[0].fragment_kind == "catalog_items"
