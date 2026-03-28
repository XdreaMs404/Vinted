from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
import uuid
from typing import Any

from vinted_radar.models import ListingCard

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

_EVENT_NAMESPACE = uuid.UUID("7b5ca7b1-1ed1-4a2b-bd35-6e5e31b2b8b9")
_SAFE_SEGMENT_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    schema_version: int
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str
    producer: str
    partition_key: str
    payload: dict[str, JsonValue]
    metadata: dict[str, JsonValue]
    payload_checksum: str

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        for field_name, value in (
            ("event_id", self.event_id),
            ("event_type", self.event_type),
            ("aggregate_type", self.aggregate_type),
            ("aggregate_id", self.aggregate_id),
            ("occurred_at", self.occurred_at),
            ("producer", self.producer),
            ("partition_key", self.partition_key),
            ("payload_checksum", self.payload_checksum),
        ):
            if not str(value).strip():
                raise ValueError(f"{field_name} cannot be empty")

        object.__setattr__(self, "payload", ensure_json_object(self.payload, field_name="payload"))
        object.__setattr__(self, "metadata", ensure_json_object(self.metadata, field_name="metadata"))

    @classmethod
    def create(
        cls,
        *,
        schema_version: int,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str | int,
        occurred_at: str,
        producer: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
        partition_key: str | int | None = None,
        identity: Mapping[str, Any] | None = None,
    ) -> EventEnvelope:
        normalized_payload = ensure_json_object(payload, field_name="payload")
        normalized_metadata = ensure_json_object(metadata or {}, field_name="metadata")
        resolved_aggregate_id = str(aggregate_id)
        resolved_partition_key = str(resolved_aggregate_id if partition_key is None else partition_key)
        payload_checksum = sha256_hex(canonical_json(normalized_payload))
        identity_payload = ensure_json_object(
            identity
            or {
                "occurred_at": occurred_at,
                "payload": normalized_payload,
                "metadata": normalized_metadata,
            },
            field_name="identity",
        )
        event_id = deterministic_uuid(
            "event-envelope",
            {
                "schema_version": schema_version,
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": resolved_aggregate_id,
                "producer": producer,
                "partition_key": resolved_partition_key,
                "identity": identity_payload,
            },
        )
        return cls(
            schema_version=schema_version,
            event_id=event_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=resolved_aggregate_id,
            occurred_at=occurred_at,
            producer=producer,
            partition_key=resolved_partition_key,
            payload=normalized_payload,
            metadata=normalized_metadata,
            payload_checksum=payload_checksum,
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at,
            "producer": self.producer,
            "partition_key": self.partition_key,
            "payload": ensure_json_object(self.payload, field_name="payload"),
            "metadata": ensure_json_object(self.metadata, field_name="metadata"),
            "payload_checksum": self.payload_checksum,
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())

    def object_key(self, prefix: str) -> str:
        normalized_prefix = normalize_prefix(prefix)
        type_segment = sanitize_storage_segment(self.event_type)
        return f"{normalized_prefix}/v{self.schema_version}/{type_segment}/{self.event_id}.json"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EventEnvelope:
        return cls(
            schema_version=int(payload["schema_version"]),
            event_id=str(payload["event_id"]),
            event_type=str(payload["event_type"]),
            aggregate_type=str(payload["aggregate_type"]),
            aggregate_id=str(payload["aggregate_id"]),
            occurred_at=str(payload["occurred_at"]),
            producer=str(payload["producer"]),
            partition_key=str(payload["partition_key"]),
            payload=ensure_json_object(payload.get("payload") or {}, field_name="payload"),
            metadata=ensure_json_object(payload.get("metadata") or {}, field_name="metadata"),
            payload_checksum=str(payload["payload_checksum"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> EventEnvelope:
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            raise ValueError("EventEnvelope JSON must decode to an object")
        return cls.from_dict(decoded)


def build_listing_observed_event(
    listing: ListingCard,
    *,
    run_id: str,
    observed_at: str,
    source_page_number: int,
    card_position: int,
    source_catalog_id: int | None = None,
    source_root_catalog_id: int | None = None,
    schema_version: int = 1,
    producer: str = "vinted_radar.parsers.api_catalog_page",
    capture_source: str = "api_catalog_page",
) -> EventEnvelope:
    resolved_catalog_id = listing.source_catalog_id if source_catalog_id is None else source_catalog_id
    resolved_root_catalog_id = (
        listing.source_root_catalog_id if source_root_catalog_id is None else source_root_catalog_id
    )
    payload = listing_payload_from_card(listing)
    metadata = {
        "run_id": run_id,
        "source_catalog_id": resolved_catalog_id,
        "source_root_catalog_id": resolved_root_catalog_id,
        "source_page_number": source_page_number,
        "card_position": card_position,
        "capture_source": capture_source,
    }
    identity = {
        "run_id": run_id,
        "listing_id": listing.listing_id,
        "observed_at": observed_at,
        "source_catalog_id": resolved_catalog_id,
        "source_root_catalog_id": resolved_root_catalog_id,
        "source_page_number": source_page_number,
        "card_position": card_position,
    }
    partition_key = resolved_root_catalog_id if resolved_root_catalog_id is not None else listing.listing_id
    return EventEnvelope.create(
        schema_version=schema_version,
        event_type="vinted.listing.observed",
        aggregate_type="listing",
        aggregate_id=listing.listing_id,
        occurred_at=observed_at,
        producer=producer,
        partition_key=partition_key,
        payload=payload,
        metadata={key: value for key, value in metadata.items() if value is not None},
        identity={key: value for key, value in identity.items() if value is not None},
    )


def listing_payload_from_card(listing: ListingCard) -> dict[str, JsonValue]:
    return ensure_json_object(
        {
            "listing_id": listing.listing_id,
            "canonical_url": listing.canonical_url,
            "source_url": listing.source_url,
            "title": listing.title,
            "brand": listing.brand,
            "size_label": listing.size_label,
            "condition_label": listing.condition_label,
            "price_amount_cents": listing.price_amount_cents,
            "price_currency": listing.price_currency,
            "total_price_amount_cents": listing.total_price_amount_cents,
            "total_price_currency": listing.total_price_currency,
            "image_url": listing.image_url,
            "favourite_count": listing.favourite_count,
            "view_count": listing.view_count,
            "user_id": listing.user_id,
            "user_login": listing.user_login,
            "user_profile_url": listing.user_profile_url,
            "created_at_ts": listing.created_at_ts,
            "raw_card": dict(listing.raw_card),
        },
        field_name="listing payload",
    )


def ensure_json_object(value: Mapping[str, Any] | None, *, field_name: str) -> dict[str, JsonValue]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return {str(key): normalize_json_value(item) for key, item in value.items()}


def normalize_json_value(value: Any) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON values cannot contain NaN or Infinity")
        return value
    if isinstance(value, Mapping):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [normalize_json_value(item) for item in value]
        return sorted(normalized_items, key=canonical_json)
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        normalize_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return sha256(payload).hexdigest()


def deterministic_uuid(label: str, value: Mapping[str, Any] | Sequence[Any] | str) -> str:
    material = canonical_json({"label": label, "value": normalize_json_value(value)})
    return str(uuid.uuid5(_EVENT_NAMESPACE, material))


def normalize_prefix(prefix: str) -> str:
    candidate = str(prefix).replace("\\", "/").strip().strip("/")
    segments = [segment.strip() for segment in candidate.split("/") if segment.strip()]
    if not segments:
        raise ValueError("prefix cannot be empty")
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("prefix cannot contain '.' or '..' segments")
    return "/".join(segments)


def sanitize_storage_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("-", value.strip().lower()).strip("-")
    return cleaned or "event"


__all__ = [
    "EventEnvelope",
    "JsonValue",
    "build_listing_observed_event",
    "canonical_json",
    "deterministic_uuid",
    "ensure_json_object",
    "listing_payload_from_card",
    "normalize_json_value",
    "normalize_prefix",
    "sanitize_storage_segment",
    "sha256_hex",
]
