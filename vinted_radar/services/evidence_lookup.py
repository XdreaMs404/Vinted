from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from vinted_radar.domain.events import EventEnvelope
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.object_store import S3ObjectStore


@dataclass(frozen=True, slots=True)
class EvidenceLookupResult:
    event: EventEnvelope
    event_key: str
    manifest: EvidenceManifest
    manifest_key: str
    parquet_object_key: str
    row_count: int
    matched_row_index: int | None
    matched_row: dict[str, object] | None
    fragment_root: str
    fragment_path: str | None
    fragment: object

    def as_dict(self) -> dict[str, object]:
        return {
            "event": self.event.as_dict(),
            "event_key": self.event_key,
            "manifest": self.manifest.as_dict(),
            "manifest_key": self.manifest_key,
            "parquet_object_key": self.parquet_object_key,
            "row_count": self.row_count,
            "matched_row_index": self.matched_row_index,
            "matched_row": self.matched_row,
            "fragment_root": self.fragment_root,
            "fragment_path": self.fragment_path,
            "fragment": self.fragment,
        }


class EvidenceLookupService:
    def __init__(
        self,
        object_store: S3ObjectStore,
        *,
        raw_events_prefix: str,
        manifests_prefix: str,
        closeables: Sequence[object] = (),
    ) -> None:
        self.object_store = object_store
        self.raw_events_prefix = raw_events_prefix
        self.manifests_prefix = manifests_prefix
        self._closeables = tuple(closeables)

    @classmethod
    def from_config(
        cls,
        *,
        config: PlatformConfig | None = None,
        s3_client: object | None = None,
    ) -> EvidenceLookupService:
        resolved_config = load_platform_config() if config is None else config
        object_store = S3ObjectStore.from_config(resolved_config, client=s3_client)
        closeables = [] if s3_client is not None else [object_store.client]
        return cls(
            object_store,
            raw_events_prefix=resolved_config.storage.raw_events,
            manifests_prefix=resolved_config.storage.manifests,
            closeables=closeables,
        )

    def close(self) -> None:
        for resource in self._closeables:
            _close_resource_quietly(resource)

    def inspect(
        self,
        *,
        event_id: str | None = None,
        manifest_id: str | None = None,
        event_key: str | None = None,
        manifest_key: str | None = None,
        row_index: int | None = None,
        listing_id: int | None = None,
        probe_id: str | None = None,
        field_path: str | None = None,
    ) -> EvidenceLookupResult:
        reference_count = sum(
            1
            for value in (event_id, manifest_id, event_key, manifest_key)
            if value not in {None, ""}
        )
        if reference_count != 1:
            raise ValueError("Provide exactly one of --event-id, --manifest-id, --event-key, or --manifest-key.")

        resolved_manifest_key = manifest_key
        resolved_event_key = event_key
        manifest: EvidenceManifest | None = None
        event: EventEnvelope | None = None

        if manifest_key is not None:
            manifest = EvidenceManifest.from_json(self.object_store.get_text(manifest_key))
        elif manifest_id is not None:
            resolved_manifest_key = self._find_manifest_key(manifest_id)
            manifest = EvidenceManifest.from_json(self.object_store.get_text(resolved_manifest_key))

        if event_key is not None:
            event = EventEnvelope.from_json(self.object_store.get_text(event_key))
        elif event_id is not None:
            resolved_event_key = self._find_event_key(event_id)
            event = EventEnvelope.from_json(self.object_store.get_text(resolved_event_key))

        if manifest is None:
            if event is None:
                raise RuntimeError("Event lookup should resolve an event before resolving a manifest.")
            resolved_manifest_key = self._find_manifest_key_for_event(event.event_id)
            manifest = EvidenceManifest.from_json(self.object_store.get_text(resolved_manifest_key))

        if event is None:
            resolved_event_key = self._find_event_key(manifest.event_id)
            event = EventEnvelope.from_json(self.object_store.get_text(resolved_event_key))

        if manifest.event_id != event.event_id:
            raise ValueError(
                f"Resolved manifest {manifest.manifest_id} belongs to event {manifest.event_id}, not {event.event_id}."
            )

        parquet_entry = self._entry_by_logical_name(manifest, logical_name="parquet-batch")
        rows = self._read_parquet_rows(parquet_entry.object_key)

        needs_row = field_path is None or not field_path.startswith(("event.", "manifest."))
        matched_row: dict[str, object] | None = None
        matched_row_index: int | None = None
        if row_index is not None or listing_id is not None or probe_id is not None:
            matched_row, matched_row_index = self._select_row(
                rows,
                row_index=row_index,
                listing_id=listing_id,
                probe_id=probe_id,
            )
        elif needs_row:
            if len(rows) != 1:
                raise ValueError(
                    "Batch contains multiple rows; provide --row-index, --listing-id, or --probe-id to resolve a concrete fragment. "
                    f"Available preview: {self._row_preview(rows)}"
                )
            matched_row = rows[0]
            matched_row_index = _optional_int(rows[0].get("row_index")) or 0

        fragment_root, fragment = self._resolve_fragment(
            event=event,
            manifest=manifest,
            matched_row=matched_row,
            field_path=field_path,
        )
        return EvidenceLookupResult(
            event=event,
            event_key=resolved_event_key,
            manifest=manifest,
            manifest_key=resolved_manifest_key,
            parquet_object_key=parquet_entry.object_key,
            row_count=len(rows),
            matched_row_index=matched_row_index,
            matched_row=matched_row,
            fragment_root=fragment_root,
            fragment_path=field_path,
            fragment=fragment,
        )

    def _find_event_key(self, event_id: str) -> str:
        suffix = f"/{str(event_id).strip()}.json"
        return self._find_unique_key(
            prefix=self.raw_events_prefix,
            predicate=lambda key: key.endswith(suffix),
            description=f"event {event_id}",
        )

    def _find_manifest_key(self, manifest_id: str) -> str:
        suffix = f"/{str(manifest_id).strip()}.json"
        return self._find_unique_key(
            prefix=self.manifests_prefix,
            predicate=lambda key: key.endswith(suffix),
            description=f"manifest {manifest_id}",
        )

    def _find_manifest_key_for_event(self, event_id: str) -> str:
        segment = f"/{str(event_id).strip()}/"
        return self._find_unique_key(
            prefix=self.manifests_prefix,
            predicate=lambda key: segment in key and key.endswith(".json"),
            description=f"manifest for event {event_id}",
        )

    def _find_unique_key(
        self,
        *,
        prefix: str,
        predicate,
        description: str,
    ) -> str:
        keys = [key for key in self.object_store.list_keys(prefix) if predicate(key)]
        if not keys:
            raise FileNotFoundError(f"Could not resolve {description} under object-store prefix '{prefix}'.")
        if len(keys) > 1:
            preview = ", ".join(keys[:3])
            suffix = "" if len(keys) <= 3 else f" … ({len(keys)} matches)"
            raise ValueError(f"Resolved {description} to multiple object keys: {preview}{suffix}")
        return keys[0]

    def _entry_by_logical_name(self, manifest: EvidenceManifest, *, logical_name: str) -> EvidenceManifestEntry:
        for entry in manifest.entries:
            if entry.logical_name == logical_name:
                return entry
        raise ValueError(f"Manifest {manifest.manifest_id} does not contain a '{logical_name}' entry.")

    def _read_parquet_rows(self, key: str) -> list[dict[str, object]]:
        result = self.object_store.get_bytes(key)
        rows = pq.read_table(pa.BufferReader(result.data)).to_pylist()
        return [_decode_serialized_value(row) for row in rows]

    def _select_row(
        self,
        rows: Sequence[dict[str, object]],
        *,
        row_index: int | None,
        listing_id: int | None,
        probe_id: str | None,
    ) -> tuple[dict[str, object], int]:
        matches: list[tuple[int, dict[str, object]]] = []
        for fallback_index, row in enumerate(rows):
            candidate_row_index = _optional_int(row.get("row_index"))
            if row_index is not None and candidate_row_index != row_index:
                continue
            if listing_id is not None and _optional_int(row.get("listing_id")) != listing_id:
                continue
            if probe_id is not None and str(row.get("probe_id") or "") != probe_id:
                continue
            matches.append((fallback_index if candidate_row_index is None else candidate_row_index, row))

        if not matches:
            raise FileNotFoundError(
                "No evidence row matched the requested selector. "
                f"Available preview: {self._row_preview(rows)}"
            )
        if len(matches) > 1:
            preview = ", ".join(self._describe_row(row_index=item[0], row=item[1]) for item in matches[:5])
            suffix = "" if len(matches) <= 5 else f" … ({len(matches)} matches)"
            raise ValueError(
                "The requested selector is ambiguous across multiple rows. "
                f"Matches: {preview}{suffix}. Narrow the lookup with --row-index or --probe-id."
            )
        return matches[0][1], matches[0][0]

    def _resolve_fragment(
        self,
        *,
        event: EventEnvelope,
        manifest: EvidenceManifest,
        matched_row: dict[str, object] | None,
        field_path: str | None,
    ) -> tuple[str, object]:
        if field_path is None:
            if matched_row is None:
                raise ValueError("A row selector is required when no field path is provided.")
            return "row", matched_row

        normalized_path = field_path.strip()
        if not normalized_path:
            if matched_row is None:
                raise ValueError("A row selector is required when no field path is provided.")
            return "row", matched_row

        roots = {
            "event": event.as_dict(),
            "manifest": manifest.as_dict(),
            "row": matched_row,
        }
        if normalized_path.startswith("event."):
            return "event", _walk_path(roots["event"], normalized_path.split(".")[1:])
        if normalized_path.startswith("manifest."):
            return "manifest", _walk_path(roots["manifest"], normalized_path.split(".")[1:])
        if normalized_path.startswith("row."):
            if matched_row is None:
                raise ValueError("A row selector is required for field paths under 'row.'.")
            return "row", _walk_path(matched_row, normalized_path.split(".")[1:])
        if matched_row is None:
            raise ValueError("A row selector is required for field paths that do not start with 'event.' or 'manifest.'.")
        return "row", _walk_path(matched_row, normalized_path.split("."))

    def _row_preview(self, rows: Sequence[dict[str, object]]) -> str:
        preview_rows = [self._describe_row(row_index=index, row=row) for index, row in enumerate(rows[:5])]
        preview = ", ".join(preview_rows)
        return preview if preview else "no rows"

    def _describe_row(self, *, row_index: int, row: Mapping[str, object]) -> str:
        parts = [f"row_index={_optional_int(row.get('row_index')) if row.get('row_index') is not None else row_index}"]
        listing_id = _optional_int(row.get("listing_id"))
        if listing_id is not None:
            parts.append(f"listing_id={listing_id}")
        probe_id = row.get("probe_id")
        if probe_id not in {None, ""}:
            parts.append(f"probe_id={probe_id}")
        return "{" + ", ".join(parts) + "}"



def _decode_serialized_value(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return _decode_serialized_value(json.loads(stripped))
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(value, list):
        return [_decode_serialized_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _decode_serialized_value(item) for key, item in value.items()}
    return value



def _walk_path(root: object, parts: Sequence[str]) -> object:
    current = root
    traversed: list[str] = []
    for part in parts:
        traversed.append(part)
        if isinstance(current, Mapping):
            if part not in current:
                raise KeyError(f"Field path not found at {'.'.join(traversed)}")
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise KeyError(f"Expected a numeric list index at {'.'.join(traversed)}") from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(f"List index out of range at {'.'.join(traversed)}") from exc
            continue
        raise KeyError(f"Cannot descend into {type(current).__name__} at {'.'.join(traversed[:-1]) or '<root>'}")
    return current



def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _close_resource_quietly(resource: object) -> None:
    for method_name in ("close", "close_connections"):
        method = getattr(resource, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:  # noqa: BLE001
                pass
            return


__all__ = [
    "EvidenceLookupResult",
    "EvidenceLookupService",
]
