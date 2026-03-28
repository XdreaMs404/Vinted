from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from vinted_radar.card_payload import normalize_card_snapshot
from vinted_radar.domain.events import EventEnvelope
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.lake_writer import LakeWriteResult, ParquetLakeWriter
from vinted_radar.repository import RadarRepository

EVIDENCE_EXPORT_DATASETS = ("discoveries", "observations", "probes")


@dataclass(frozen=True, slots=True)
class HistoricalEvidenceBatch:
    dataset: str
    group_key: str
    batch_index: int
    row_count: int
    event_id: str
    event_type: str
    manifest_id: str
    event_object_key: str
    parquet_object_key: str
    manifest_object_key: str

    def as_dict(self) -> dict[str, object]:
        return {
            "dataset": self.dataset,
            "group_key": self.group_key,
            "batch_index": self.batch_index,
            "row_count": self.row_count,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "manifest_id": self.manifest_id,
            "event_object_key": self.event_object_key,
            "parquet_object_key": self.parquet_object_key,
            "manifest_object_key": self.manifest_object_key,
        }


@dataclass(frozen=True, slots=True)
class HistoricalEvidenceExportReport:
    db_path: str
    datasets: tuple[str, ...]
    batch_size: int
    batch_counts: dict[str, int]
    row_counts: dict[str, int]
    batches: tuple[HistoricalEvidenceBatch, ...]

    @property
    def total_batches(self) -> int:
        return sum(self.batch_counts.values())

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())

    def as_dict(self) -> dict[str, object]:
        return {
            "db_path": self.db_path,
            "datasets": list(self.datasets),
            "batch_size": self.batch_size,
            "total_batches": self.total_batches,
            "total_rows": self.total_rows,
            "batch_counts": dict(self.batch_counts),
            "row_counts": dict(self.row_counts),
            "batches": [batch.as_dict() for batch in self.batches],
        }


@dataclass(frozen=True, slots=True)
class _PreparedExportBatch:
    dataset: str
    group_key: str
    rows: tuple[dict[str, object], ...]
    batch_event: EventEnvelope
    manifest_type: str
    manifest_metadata: dict[str, object]


class HistoricalEvidenceExporter:
    def __init__(
        self,
        repository: RadarRepository,
        lake_writer: ParquetLakeWriter,
        *,
        event_schema_version: int = 1,
        closeables: Sequence[object] = (),
    ) -> None:
        self.repository = repository
        self.lake_writer = lake_writer
        self.event_schema_version = int(event_schema_version)
        self._closeables = tuple(closeables)

    @classmethod
    def from_config(
        cls,
        *,
        db_path: str | Path,
        config: PlatformConfig | None = None,
        s3_client: object | None = None,
    ) -> HistoricalEvidenceExporter:
        resolved_config = load_platform_config() if config is None else config
        writer = ParquetLakeWriter.from_config(resolved_config, client=s3_client)
        closeables = [] if s3_client is not None else [writer.object_store.client]
        return cls(
            RadarRepository(db_path),
            writer,
            event_schema_version=resolved_config.schema_versions.events,
            closeables=closeables,
        )

    def close(self) -> None:
        self.repository.close()
        for resource in self._closeables:
            _close_resource_quietly(resource)

    def export(
        self,
        *,
        datasets: Sequence[str] = (),
        batch_size: int = 500,
    ) -> HistoricalEvidenceExportReport:
        resolved_datasets = normalize_export_datasets(datasets)
        bounded_batch_size = max(int(batch_size), 1)
        batch_counts = {dataset: 0 for dataset in resolved_datasets}
        row_counts = {dataset: 0 for dataset in resolved_datasets}
        batches: list[HistoricalEvidenceBatch] = []

        self.lake_writer.object_store.ensure_bucket()

        for dataset in resolved_datasets:
            for prepared in self._iter_dataset_batches(dataset, batch_size=bounded_batch_size):
                lake_write = self.lake_writer.write_batch(
                    batch_event=prepared.batch_event,
                    rows=prepared.rows,
                    manifest_type=prepared.manifest_type,
                    manifest_metadata=prepared.manifest_metadata,
                )
                batch_counts[dataset] += 1
                row_counts[dataset] += len(prepared.rows)
                batches.append(
                    _batch_from_lake_write(
                        dataset=dataset,
                        group_key=prepared.group_key,
                        batch_index=batch_counts[dataset] - 1,
                        lake_write=lake_write,
                    )
                )

        return HistoricalEvidenceExportReport(
            db_path=str(self.repository.db_path),
            datasets=resolved_datasets,
            batch_size=bounded_batch_size,
            batch_counts=batch_counts,
            row_counts=row_counts,
            batches=tuple(batches),
        )

    def _iter_dataset_batches(self, dataset: str, *, batch_size: int):
        if dataset == "discoveries":
            yield from self._iter_discovery_batches(batch_size=batch_size)
            return
        if dataset == "observations":
            yield from self._iter_observation_batches(batch_size=batch_size)
            return
        if dataset == "probes":
            yield from self._iter_probe_batches(batch_size=batch_size)
            return
        raise ValueError(f"Unsupported historical evidence dataset: {dataset}")

    def _iter_discovery_batches(self, *, batch_size: int):
        cursor = self.repository.connection.execute(
            """
            SELECT
                discoveries.run_id,
                discoveries.listing_id,
                discoveries.observed_at,
                discoveries.source_catalog_id,
                discoveries.source_page_number,
                discoveries.source_url,
                discoveries.card_position,
                discoveries.raw_card_payload_json,
                listings.canonical_url AS listing_canonical_url,
                listings.title AS listing_title,
                listings.brand AS listing_brand,
                listings.size_label AS listing_size_label,
                listings.condition_label AS listing_condition_label,
                listings.price_amount_cents AS listing_price_amount_cents,
                listings.price_currency AS listing_price_currency,
                listings.total_price_amount_cents AS listing_total_price_amount_cents,
                listings.total_price_currency AS listing_total_price_currency,
                listings.image_url AS listing_image_url,
                listings.primary_catalog_id AS listing_primary_catalog_id,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id,
                source_catalog.root_catalog_id AS source_root_catalog_id,
                source_catalog.root_title AS source_root_title,
                source_catalog.title AS source_catalog_title,
                source_catalog.path AS source_catalog_path,
                primary_catalog.title AS primary_catalog_title,
                primary_catalog.path AS primary_catalog_path,
                resolved_root.title AS resolved_root_title
            FROM listing_discoveries AS discoveries
            LEFT JOIN listings ON listings.listing_id = discoveries.listing_id
            LEFT JOIN catalogs AS source_catalog ON source_catalog.catalog_id = discoveries.source_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN catalogs AS resolved_root
              ON resolved_root.catalog_id = COALESCE(source_catalog.root_catalog_id, primary_catalog.root_catalog_id, listings.primary_root_catalog_id)
            ORDER BY
                discoveries.run_id ASC,
                discoveries.source_catalog_id ASC,
                discoveries.source_page_number ASC,
                discoveries.observed_at ASC,
                discoveries.listing_id ASC
            """
        )

        current_group: tuple[str, int | None, int | None] | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0

        for row in cursor:
            hydrated = _hydrate_discovery_row(row)
            group = (
                str(hydrated["run_id"]),
                _optional_int(hydrated.get("catalog_id")),
                _optional_int(hydrated.get("page_number")),
            )
            if current_group is None:
                current_group = group
            if group != current_group or len(current_rows) >= batch_size:
                yield self._prepare_discovery_batch(current_group, current_rows, chunk_index=chunk_index)
                if group != current_group:
                    current_group = group
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(hydrated)

        if current_group is not None and current_rows:
            yield self._prepare_discovery_batch(current_group, current_rows, chunk_index=chunk_index)

    def _prepare_discovery_batch(
        self,
        group: tuple[str, int | None, int | None],
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedExportBatch:
        run_id, catalog_id, page_number = group
        first = rows[0]
        occurred_at = str(first["observed_at"])
        listing_ids = [int(row["listing_id"]) for row in rows]
        partition_key = first.get("root_catalog_id") or catalog_id or run_id
        group_key = (
            f"run_id={run_id}/catalog_id={catalog_id if catalog_id is not None else 'none'}"
            f"/page_number={page_number if page_number is not None else 'none'}/chunk={chunk_index}"
        )
        batch_event = EventEnvelope.create(
            schema_version=self.event_schema_version,
            event_type="vinted.backfill.discovery.batch",
            aggregate_type="discovery-run-page",
            aggregate_id=f"{run_id}:{catalog_id if catalog_id is not None else 'none'}:{page_number if page_number is not None else 'none'}",
            occurred_at=occurred_at,
            producer="vinted_radar.services.evidence_export",
            partition_key=partition_key,
            payload={
                "source_table": "listing_discoveries",
                "run_id": run_id,
                "catalog_id": catalog_id,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "listing_ids": listing_ids,
            },
            metadata={
                "capture_source": "sqlite_backfill",
                "root_catalog_id": first.get("root_catalog_id"),
                "root_title": first.get("root_title"),
                "catalog_title": first.get("catalog_title"),
                "catalog_path": first.get("catalog_path"),
            },
        )
        return _PreparedExportBatch(
            dataset="discoveries",
            group_key=group_key,
            rows=tuple(rows),
            batch_event=batch_event,
            manifest_type="sqlite-discovery-evidence-batch",
            manifest_metadata={
                "legacy_dataset": "discoveries",
                "source_table": "listing_discoveries",
                "group_key": group_key,
                "run_id": run_id,
                "catalog_id": catalog_id,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "first_observed_at": rows[0].get("observed_at"),
                "last_observed_at": rows[-1].get("observed_at"),
            },
        )

    def _iter_observation_batches(self, *, batch_size: int):
        cursor = self.repository.connection.execute(
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
                observations.title AS observation_title,
                observations.brand AS observation_brand,
                observations.size_label AS observation_size_label,
                observations.condition_label AS observation_condition_label,
                observations.price_amount_cents AS observation_price_amount_cents,
                observations.price_currency AS observation_price_currency,
                observations.total_price_amount_cents AS observation_total_price_amount_cents,
                observations.total_price_currency AS observation_total_price_currency,
                observations.image_url AS observation_image_url,
                observations.raw_card_payload_json,
                listings.primary_catalog_id AS listing_primary_catalog_id,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id,
                source_catalog.root_catalog_id AS source_root_catalog_id,
                source_catalog.root_title AS source_root_title,
                source_catalog.title AS source_catalog_title,
                source_catalog.path AS source_catalog_path,
                primary_catalog.title AS primary_catalog_title,
                primary_catalog.path AS primary_catalog_path,
                resolved_root.title AS resolved_root_title
            FROM listing_observations AS observations
            LEFT JOIN listings ON listings.listing_id = observations.listing_id
            LEFT JOIN catalogs AS source_catalog ON source_catalog.catalog_id = observations.source_catalog_id
            LEFT JOIN catalogs AS primary_catalog ON primary_catalog.catalog_id = listings.primary_catalog_id
            LEFT JOIN catalogs AS resolved_root
              ON resolved_root.catalog_id = COALESCE(source_catalog.root_catalog_id, primary_catalog.root_catalog_id, listings.primary_root_catalog_id)
            ORDER BY
                observations.run_id ASC,
                observations.observed_at ASC,
                observations.listing_id ASC
            """
        )

        current_run_id: str | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0

        for row in cursor:
            hydrated = _hydrate_observation_row(row)
            run_id = str(hydrated["run_id"])
            if current_run_id is None:
                current_run_id = run_id
            if run_id != current_run_id or len(current_rows) >= batch_size:
                yield self._prepare_observation_batch(current_run_id, current_rows, chunk_index=chunk_index)
                if run_id != current_run_id:
                    current_run_id = run_id
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(hydrated)

        if current_run_id is not None and current_rows:
            yield self._prepare_observation_batch(current_run_id, current_rows, chunk_index=chunk_index)

    def _prepare_observation_batch(
        self,
        run_id: str,
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedExportBatch:
        first = rows[0]
        root_titles = sorted({str(row["root_title"]) for row in rows if row.get("root_title")})
        listing_ids = [int(row["listing_id"]) for row in rows]
        partition_key = first.get("root_catalog_id") or run_id
        group_key = f"run_id={run_id}/chunk={chunk_index}"
        batch_event = EventEnvelope.create(
            schema_version=self.event_schema_version,
            event_type="vinted.backfill.observation.batch",
            aggregate_type="discovery-run",
            aggregate_id=run_id,
            occurred_at=str(first["observed_at"]),
            producer="vinted_radar.services.evidence_export",
            partition_key=partition_key,
            payload={
                "source_table": "listing_observations",
                "run_id": run_id,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "listing_ids": listing_ids,
            },
            metadata={
                "capture_source": "sqlite_backfill",
                "root_titles": root_titles,
            },
        )
        return _PreparedExportBatch(
            dataset="observations",
            group_key=group_key,
            rows=tuple(rows),
            batch_event=batch_event,
            manifest_type="sqlite-observation-evidence-batch",
            manifest_metadata={
                "legacy_dataset": "observations",
                "source_table": "listing_observations",
                "group_key": group_key,
                "run_id": run_id,
                "chunk_index": chunk_index,
                "first_observed_at": rows[0].get("observed_at"),
                "last_observed_at": rows[-1].get("observed_at"),
                "root_titles": root_titles,
            },
        )

    def _iter_probe_batches(self, *, batch_size: int):
        cursor = self.repository.connection.execute(
            """
            SELECT
                probes.probe_id,
                probes.listing_id,
                probes.probed_at,
                probes.requested_url,
                probes.final_url,
                probes.response_status,
                probes.probe_outcome,
                probes.detail_json,
                probes.error_message,
                listings.title AS listing_title,
                listings.canonical_url AS listing_canonical_url,
                listings.primary_root_catalog_id AS listing_primary_root_catalog_id
            FROM item_page_probes AS probes
            LEFT JOIN listings ON listings.listing_id = probes.listing_id
            ORDER BY
                substr(probes.probed_at, 1, 10) ASC,
                probes.probed_at ASC,
                probes.probe_id ASC
            """
        )

        current_day: str | None = None
        current_rows: list[dict[str, object]] = []
        chunk_index = 0

        for row in cursor:
            hydrated = _hydrate_probe_row(row)
            probed_on = str(hydrated["probed_at"])[:10]
            if current_day is None:
                current_day = probed_on
            if probed_on != current_day or len(current_rows) >= batch_size:
                yield self._prepare_probe_batch(current_day, current_rows, chunk_index=chunk_index)
                if probed_on != current_day:
                    current_day = probed_on
                    current_rows = []
                    chunk_index = 0
                else:
                    current_rows = []
                    chunk_index += 1
            current_rows.append(hydrated)

        if current_day is not None and current_rows:
            yield self._prepare_probe_batch(current_day, current_rows, chunk_index=chunk_index)

    def _prepare_probe_batch(
        self,
        probed_on: str,
        rows: Sequence[dict[str, object]],
        *,
        chunk_index: int,
    ) -> _PreparedExportBatch:
        first = rows[0]
        probe_ids = [str(row["probe_id"]) for row in rows]
        listing_ids = [int(row["listing_id"]) for row in rows]
        partition_key = first.get("listing_id") or probed_on
        group_key = f"probed_on={probed_on}/chunk={chunk_index}"
        batch_event = EventEnvelope.create(
            schema_version=self.event_schema_version,
            event_type="vinted.backfill.probe.batch",
            aggregate_type="probe-day",
            aggregate_id=probed_on,
            occurred_at=str(first["probed_at"]),
            producer="vinted_radar.services.evidence_export",
            partition_key=partition_key,
            payload={
                "source_table": "item_page_probes",
                "probed_on": probed_on,
                "chunk_index": chunk_index,
                "row_count": len(rows),
                "probe_ids": probe_ids,
                "listing_ids": listing_ids,
            },
            metadata={
                "capture_source": "sqlite_backfill",
            },
        )
        return _PreparedExportBatch(
            dataset="probes",
            group_key=group_key,
            rows=tuple(rows),
            batch_event=batch_event,
            manifest_type="sqlite-probe-evidence-batch",
            manifest_metadata={
                "legacy_dataset": "probes",
                "source_table": "item_page_probes",
                "group_key": group_key,
                "probed_on": probed_on,
                "chunk_index": chunk_index,
                "first_probed_at": rows[0].get("probed_at"),
                "last_probed_at": rows[-1].get("probed_at"),
            },
        )


def normalize_export_datasets(datasets: Sequence[str] = ()) -> tuple[str, ...]:
    if not datasets:
        return EVIDENCE_EXPORT_DATASETS

    requested = [str(item).strip().lower() for item in datasets if str(item).strip()]
    if not requested or "all" in requested:
        return EVIDENCE_EXPORT_DATASETS

    invalid = sorted({item for item in requested if item not in EVIDENCE_EXPORT_DATASETS})
    if invalid:
        raise ValueError(
            f"Unsupported datasets: {', '.join(invalid)}. Expected one or more of: all, discoveries, observations, probes."
        )

    ordered: list[str] = []
    for dataset in EVIDENCE_EXPORT_DATASETS:
        if dataset in requested and dataset not in ordered:
            ordered.append(dataset)
    return tuple(ordered)


def _batch_from_lake_write(
    *,
    dataset: str,
    group_key: str,
    batch_index: int,
    lake_write: LakeWriteResult,
) -> HistoricalEvidenceBatch:
    return HistoricalEvidenceBatch(
        dataset=dataset,
        group_key=group_key,
        batch_index=batch_index,
        row_count=lake_write.row_count,
        event_id=lake_write.batch_event.event_id,
        event_type=lake_write.batch_event.event_type,
        manifest_id=lake_write.manifest.manifest_id,
        event_object_key=lake_write.event_object.key,
        parquet_object_key=lake_write.parquet_object.key,
        manifest_object_key=lake_write.manifest_object.key,
    )


def _hydrate_discovery_row(row: Mapping[str, Any]) -> dict[str, object]:
    record = dict(row)
    raw_card = _load_json_object(record.get("raw_card_payload_json"), field_name="raw_card_payload_json")
    source_url = str(record.get("source_url") or "")
    normalized = normalize_card_snapshot(
        raw_card_payload=raw_card,
        source_url=source_url,
        canonical_url=_optional_str(record.get("listing_canonical_url")),
        image_url=_optional_str(record.get("listing_image_url")),
    )
    catalog_id = _optional_int(record.get("source_catalog_id")) or _optional_int(record.get("listing_primary_catalog_id"))
    root_catalog_id = _optional_int(record.get("source_root_catalog_id")) or _optional_int(record.get("listing_primary_root_catalog_id"))
    return {
        "source_table": "listing_discoveries",
        "run_id": str(record["run_id"]),
        "observed_at": str(record["observed_at"]),
        "catalog_id": catalog_id,
        "root_catalog_id": root_catalog_id,
        "root_title": _optional_str(record.get("resolved_root_title")) or _optional_str(record.get("source_root_title")),
        "catalog_title": _optional_str(record.get("source_catalog_title")) or _optional_str(record.get("primary_catalog_title")),
        "catalog_path": _optional_str(record.get("source_catalog_path")) or _optional_str(record.get("primary_catalog_path")),
        "page_number": _optional_int(record.get("source_page_number")),
        "card_position": _optional_int(record.get("card_position")),
        "listing_id": int(record["listing_id"]),
        "canonical_url": _optional_str(record.get("listing_canonical_url")) or _optional_str(normalized.get("canonical_url")),
        "source_url": source_url,
        "title": _coalesce(_optional_str(record.get("listing_title")), _optional_str(normalized.get("title"))),
        "brand": _coalesce(_optional_str(record.get("listing_brand")), _optional_str(normalized.get("brand"))),
        "size_label": _coalesce(_optional_str(record.get("listing_size_label")), _optional_str(normalized.get("size_label"))),
        "condition_label": _coalesce(
            _optional_str(record.get("listing_condition_label")),
            _optional_str(normalized.get("condition_label")),
        ),
        "price_amount_cents": _coalesce(_optional_int(record.get("listing_price_amount_cents")), _optional_int(normalized.get("price_amount_cents"))),
        "price_currency": _coalesce(_optional_str(record.get("listing_price_currency")), _optional_str(normalized.get("price_currency"))),
        "total_price_amount_cents": _coalesce(
            _optional_int(record.get("listing_total_price_amount_cents")),
            _optional_int(normalized.get("total_price_amount_cents")),
        ),
        "total_price_currency": _coalesce(
            _optional_str(record.get("listing_total_price_currency")),
            _optional_str(normalized.get("total_price_currency")),
        ),
        "image_url": _coalesce(_optional_str(record.get("listing_image_url")), _optional_str(normalized.get("image_url"))),
        "raw_card": raw_card,
    }



def _hydrate_observation_row(row: Mapping[str, Any]) -> dict[str, object]:
    record = dict(row)
    raw_card = _load_json_object(record.get("raw_card_payload_json"), field_name="raw_card_payload_json")
    source_url = str(record.get("source_url") or "")
    canonical_url = _optional_str(record.get("canonical_url"))
    image_url = _optional_str(record.get("observation_image_url"))
    normalized = normalize_card_snapshot(
        raw_card_payload=raw_card,
        source_url=source_url,
        canonical_url=canonical_url,
        image_url=image_url,
    )
    catalog_id = _optional_int(record.get("source_catalog_id")) or _optional_int(record.get("listing_primary_catalog_id"))
    root_catalog_id = _optional_int(record.get("source_root_catalog_id")) or _optional_int(record.get("listing_primary_root_catalog_id"))
    return {
        "source_table": "listing_observations",
        "run_id": str(record["run_id"]),
        "observed_at": str(record["observed_at"]),
        "catalog_id": catalog_id,
        "root_catalog_id": root_catalog_id,
        "root_title": _optional_str(record.get("resolved_root_title")) or _optional_str(record.get("source_root_title")),
        "catalog_title": _optional_str(record.get("source_catalog_title")) or _optional_str(record.get("primary_catalog_title")),
        "catalog_path": _optional_str(record.get("source_catalog_path")) or _optional_str(record.get("primary_catalog_path")),
        "page_number": _optional_int(record.get("source_page_number")),
        "card_position": _optional_int(record.get("first_card_position")),
        "sighting_count": _optional_int(record.get("sighting_count")) or 0,
        "listing_id": int(record["listing_id"]),
        "canonical_url": _coalesce(canonical_url, _optional_str(normalized.get("canonical_url"))),
        "source_url": source_url,
        "title": _coalesce(_optional_str(record.get("observation_title")), _optional_str(normalized.get("title"))),
        "brand": _coalesce(_optional_str(record.get("observation_brand")), _optional_str(normalized.get("brand"))),
        "size_label": _coalesce(_optional_str(record.get("observation_size_label")), _optional_str(normalized.get("size_label"))),
        "condition_label": _coalesce(
            _optional_str(record.get("observation_condition_label")),
            _optional_str(normalized.get("condition_label")),
        ),
        "price_amount_cents": _coalesce(
            _optional_int(record.get("observation_price_amount_cents")),
            _optional_int(normalized.get("price_amount_cents")),
        ),
        "price_currency": _coalesce(
            _optional_str(record.get("observation_price_currency")),
            _optional_str(normalized.get("price_currency")),
        ),
        "total_price_amount_cents": _coalesce(
            _optional_int(record.get("observation_total_price_amount_cents")),
            _optional_int(normalized.get("total_price_amount_cents")),
        ),
        "total_price_currency": _coalesce(
            _optional_str(record.get("observation_total_price_currency")),
            _optional_str(normalized.get("total_price_currency")),
        ),
        "image_url": _coalesce(image_url, _optional_str(normalized.get("image_url"))),
        "raw_card": raw_card,
    }



def _hydrate_probe_row(row: Mapping[str, Any]) -> dict[str, object]:
    record = dict(row)
    return {
        "source_table": "item_page_probes",
        "probe_id": str(record["probe_id"]),
        "listing_id": int(record["listing_id"]),
        "probed_at": str(record["probed_at"]),
        "requested_url": _optional_str(record.get("requested_url")),
        "final_url": _optional_str(record.get("final_url")),
        "response_status": _optional_int(record.get("response_status")),
        "probe_outcome": _optional_str(record.get("probe_outcome")),
        "error_message": _optional_str(record.get("error_message")),
        "title": _optional_str(record.get("listing_title")),
        "canonical_url": _optional_str(record.get("listing_canonical_url")),
        "root_catalog_id": _optional_int(record.get("listing_primary_root_catalog_id")),
        "detail": _load_json_object(record.get("detail_json"), field_name="detail_json"),
    }



def _load_json_object(value: object, *, field_name: str) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    raw_text = str(value)
    try:
        decoded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return {
            "_parse_error": f"{type(exc).__name__}: {exc}",
            "_raw_text": raw_text,
            "_field_name": field_name,
        }
    if isinstance(decoded, Mapping):
        return {str(key): item for key, item in decoded.items()}
    return {
        "_non_object_json": decoded,
        "_field_name": field_name,
    }



def _coalesce(primary: object, fallback: object) -> object:
    return fallback if primary is None else primary



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
    "EVIDENCE_EXPORT_DATASETS",
    "HistoricalEvidenceBatch",
    "HistoricalEvidenceExportReport",
    "HistoricalEvidenceExporter",
    "normalize_export_datasets",
]
