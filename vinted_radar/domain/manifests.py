from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any

from vinted_radar.domain.events import (
    EventEnvelope,
    JsonValue,
    canonical_json,
    deterministic_uuid,
    ensure_json_object,
    normalize_prefix,
    sha256_hex,
)


@dataclass(frozen=True, slots=True)
class EvidenceManifestEntry:
    logical_name: str
    object_key: str
    content_type: str
    content_length: int
    checksum: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("logical_name", self.logical_name),
            ("object_key", self.object_key),
            ("content_type", self.content_type),
            ("checksum", self.checksum),
        ):
            if not str(value).strip():
                raise ValueError(f"{field_name} cannot be empty")
        if self.content_length < 0:
            raise ValueError("content_length must be >= 0")

    @classmethod
    def from_bytes(
        cls,
        *,
        logical_name: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> EvidenceManifestEntry:
        return cls(
            logical_name=logical_name,
            object_key=normalize_prefix(object_key),
            content_type=content_type,
            content_length=len(data),
            checksum=sha256_hex(data),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "logical_name": self.logical_name,
            "object_key": self.object_key,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "checksum": self.checksum,
        }


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    schema_version: int
    manifest_id: str
    event_id: str
    manifest_type: str
    generated_at: str
    bucket: str
    entries: tuple[EvidenceManifestEntry, ...]
    metadata: dict[str, JsonValue]
    checksum_algorithm: str
    checksum: str

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1")
        for field_name, value in (
            ("manifest_id", self.manifest_id),
            ("event_id", self.event_id),
            ("manifest_type", self.manifest_type),
            ("generated_at", self.generated_at),
            ("bucket", self.bucket),
            ("checksum_algorithm", self.checksum_algorithm),
            ("checksum", self.checksum),
        ):
            if not str(value).strip():
                raise ValueError(f"{field_name} cannot be empty")
        if not self.entries:
            raise ValueError("entries cannot be empty")
        object.__setattr__(self, "metadata", ensure_json_object(self.metadata, field_name="metadata"))

    @classmethod
    def create(
        cls,
        *,
        schema_version: int,
        event_id: str,
        manifest_type: str,
        generated_at: str,
        bucket: str,
        entries: list[EvidenceManifestEntry] | tuple[EvidenceManifestEntry, ...],
        metadata: Mapping[str, Any] | None = None,
        checksum_algorithm: str = "sha256",
    ) -> EvidenceManifest:
        if checksum_algorithm != "sha256":
            raise ValueError("Only sha256 manifests are supported")
        entry_tuple = tuple(entries)
        if not entry_tuple:
            raise ValueError("entries cannot be empty")
        normalized_metadata = ensure_json_object(metadata or {}, field_name="metadata")
        manifest_body = {
            "schema_version": schema_version,
            "event_id": event_id,
            "manifest_type": manifest_type,
            "generated_at": generated_at,
            "bucket": bucket,
            "entries": [entry.as_dict() for entry in entry_tuple],
            "metadata": normalized_metadata,
            "checksum_algorithm": checksum_algorithm,
        }
        manifest_id = deterministic_uuid("evidence-manifest", manifest_body)
        checksum = sha256_hex(canonical_json(manifest_body))
        return cls(
            schema_version=schema_version,
            manifest_id=manifest_id,
            event_id=event_id,
            manifest_type=manifest_type,
            generated_at=generated_at,
            bucket=bucket,
            entries=entry_tuple,
            metadata=normalized_metadata,
            checksum_algorithm=checksum_algorithm,
            checksum=checksum,
        )

    @classmethod
    def from_event(
        cls,
        event: EventEnvelope,
        *,
        bucket: str,
        entries: list[EvidenceManifestEntry] | tuple[EvidenceManifestEntry, ...],
        schema_version: int = 1,
        manifest_type: str = "event-evidence",
        generated_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> EvidenceManifest:
        combined_metadata = dict(event.metadata)
        if metadata:
            combined_metadata.update(ensure_json_object(metadata, field_name="metadata"))
        return cls.create(
            schema_version=schema_version,
            event_id=event.event_id,
            manifest_type=manifest_type,
            generated_at=event.occurred_at if generated_at is None else generated_at,
            bucket=bucket,
            entries=entries,
            metadata=combined_metadata,
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "event_id": self.event_id,
            "manifest_type": self.manifest_type,
            "generated_at": self.generated_at,
            "bucket": self.bucket,
            "entries": [entry.as_dict() for entry in self.entries],
            "metadata": ensure_json_object(self.metadata, field_name="metadata"),
            "checksum_algorithm": self.checksum_algorithm,
            "checksum": self.checksum,
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())

    def object_key(self, prefix: str) -> str:
        normalized_prefix = normalize_prefix(prefix)
        return f"{normalized_prefix}/v{self.schema_version}/{self.event_id}/{self.manifest_id}.json"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceManifest:
        entries_payload = payload.get("entries")
        if not isinstance(entries_payload, list):
            raise ValueError("entries must be a list")
        entries = tuple(
            EvidenceManifestEntry(
                logical_name=str(entry["logical_name"]),
                object_key=str(entry["object_key"]),
                content_type=str(entry["content_type"]),
                content_length=int(entry["content_length"]),
                checksum=str(entry["checksum"]),
            )
            for entry in entries_payload
        )
        return cls(
            schema_version=int(payload["schema_version"]),
            manifest_id=str(payload["manifest_id"]),
            event_id=str(payload["event_id"]),
            manifest_type=str(payload["manifest_type"]),
            generated_at=str(payload["generated_at"]),
            bucket=str(payload["bucket"]),
            entries=entries,
            metadata=ensure_json_object(payload.get("metadata") or {}, field_name="metadata"),
            checksum_algorithm=str(payload["checksum_algorithm"]),
            checksum=str(payload["checksum"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> EvidenceManifest:
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            raise ValueError("EvidenceManifest JSON must decode to an object")
        return cls.from_dict(decoded)


__all__ = [
    "EvidenceManifest",
    "EvidenceManifestEntry",
]
