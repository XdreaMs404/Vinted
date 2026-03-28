from __future__ import annotations

from vinted_radar.models import ListingCard
from vinted_radar.domain.events import EventEnvelope, build_listing_observed_event
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry


def _sample_listing() -> ListingCard:
    return ListingCard(
        listing_id=501,
        source_url="https://www.vinted.fr/items/501-robe-noire?referrer=catalog",
        canonical_url="https://www.vinted.fr/items/501-robe-noire",
        title="Robe noire",
        brand="Zara",
        size_label="M",
        condition_label="Très bon état",
        price_amount_cents=1250,
        price_currency="€",
        total_price_amount_cents=1413,
        total_price_currency="€",
        image_url="https://images1.vinted.net/t/01_12345.webp",
        favourite_count=7,
        view_count=45,
        user_id=88,
        user_login="alice",
        user_profile_url="https://www.vinted.fr/member/88",
        created_at_ts=1711092000,
        source_catalog_id=2001,
        source_root_catalog_id=1904,
        raw_card={
            "id": 501,
            "title": "Robe noire",
            "price": {"amount": "12.50", "currency_code": "EUR"},
        },
    )


def test_listing_event_envelope_is_deterministic_and_round_trips() -> None:
    listing = _sample_listing()

    first = build_listing_observed_event(
        listing,
        run_id="run-20260328-a",
        observed_at="2026-03-28T18:30:00+00:00",
        source_page_number=3,
        card_position=8,
    )
    second = build_listing_observed_event(
        listing,
        run_id="run-20260328-a",
        observed_at="2026-03-28T18:30:00+00:00",
        source_page_number=3,
        card_position=8,
    )

    assert first.event_type == "vinted.listing.observed"
    assert first.aggregate_type == "listing"
    assert first.aggregate_id == "501"
    assert first.partition_key == "1904"
    assert first.event_id == second.event_id
    assert first.payload_checksum == second.payload_checksum
    assert first.object_key("tenant-a/events/raw") == (
        f"tenant-a/events/raw/v1/vinted-listing-observed/{first.event_id}.json"
    )

    round_trip = EventEnvelope.from_json(first.to_json())

    assert round_trip == first
    assert round_trip.metadata["run_id"] == "run-20260328-a"
    assert round_trip.payload["raw_card"] == listing.raw_card


def test_evidence_manifest_ids_checksums_and_storage_keys_are_deterministic() -> None:
    listing = _sample_listing()
    event = build_listing_observed_event(
        listing,
        run_id="run-20260328-a",
        observed_at="2026-03-28T18:30:00+00:00",
        source_page_number=1,
        card_position=1,
    )
    event_entry = EvidenceManifestEntry.from_bytes(
        logical_name="event-envelope",
        object_key=event.object_key("tenant-a/events/raw"),
        data=event.to_json().encode("utf-8"),
        content_type="application/json",
    )
    card_entry = EvidenceManifestEntry.from_bytes(
        logical_name="raw-card",
        object_key="tenant-a/events/raw/raw-card-501.json",
        data=b'{"id":501,"title":"Robe noire"}',
        content_type="application/json",
    )

    first = EvidenceManifest.from_event(
        event,
        bucket="vinted-radar",
        entries=[event_entry, card_entry],
        metadata={"writer": "pytest"},
    )
    second = EvidenceManifest.from_event(
        event,
        bucket="vinted-radar",
        entries=[event_entry, card_entry],
        metadata={"writer": "pytest"},
    )

    assert first.manifest_id == second.manifest_id
    assert first.checksum == second.checksum
    assert first.object_key("tenant-a/manifests") == (
        f"tenant-a/manifests/v1/{event.event_id}/{first.manifest_id}.json"
    )

    restored = EvidenceManifest.from_json(first.to_json())

    assert restored == first
    assert restored.entries[0].checksum == event_entry.checksum
    assert restored.metadata["writer"] == "pytest"
