from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

from vinted_radar.platform.clickhouse_ingest import (
    CLICKHOUSE_INGEST_CONSUMER,
    CLICKHOUSE_OUTBOX_SINK,
)
from vinted_radar.platform.config import PlatformConfig, load_platform_config
from vinted_radar.platform.health import CutoverStatusSnapshot, summarize_cutover_state
from vinted_radar.platform.lake_writer import ParquetLakeWriter
from vinted_radar.platform.postgres_repository import (
    POSTGRES_CURRENT_STATE_CONSUMER,
    POSTGRES_CURRENT_STATE_SINK,
    PostgresMutableTruthRepository,
)
from vinted_radar.services.lifecycle import LifecycleReport, run_lifecycle_jobs
from vinted_radar.services.reconciliation import ReconciliationReport, run_reconciliation

_ATTENTION_PATH_STATUSES = frozenset({"lagging", "never-run", "not-run", "in-progress"})


@dataclass(frozen=True, slots=True)
class AuditPathStatus:
    path: str
    status: str
    detail: str
    command: str
    raw_status: str | None = None
    updated_at: str | None = None
    lag_seconds: float | None = None
    last_error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "status": self.status,
            "detail": self.detail,
            "command": self.command,
            "raw_status": self.raw_status,
            "updated_at": self.updated_at,
            "lag_seconds": self.lag_seconds,
            "last_error": self.last_error,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class PlatformAuditReport:
    sqlite_db_path: str
    generated_at: str
    cutover: CutoverStatusSnapshot
    reconciliation: ReconciliationReport
    current_state: AuditPathStatus
    analytical: AuditPathStatus
    lifecycle: AuditPathStatus
    backfill: AuditPathStatus
    overall_status: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.overall_status == "healthy"

    def as_dict(self) -> dict[str, object]:
        return {
            "sqlite_db_path": self.sqlite_db_path,
            "generated_at": self.generated_at,
            "cutover": self.cutover.as_dict(),
            "summary": {
                "reconciliation_status": self.reconciliation.overall_status,
                "current_state_status": self.current_state.status,
                "analytical_status": self.analytical.status,
                "lifecycle_status": self.lifecycle.status,
                "backfill_status": self.backfill.status,
            },
            "reconciliation": self.reconciliation.as_dict(),
            "paths": {
                "current_state": self.current_state.as_dict(),
                "analytical": self.analytical.as_dict(),
                "lifecycle": self.lifecycle.as_dict(),
                "backfill": self.backfill.as_dict(),
            },
            "overall_status": self.overall_status,
            "ok": self.ok,
            "error": self.error,
        }


class PlatformAuditService:
    def __init__(
        self,
        sqlite_db_path: str | Path,
        *,
        config: PlatformConfig | None = None,
        reference_now: str | None = None,
        checkpoint_path: str | Path | None = None,
        repository: PostgresMutableTruthRepository | object | None = None,
        lake_writer: ParquetLakeWriter | None = None,
        clickhouse_client: object | None = None,
        object_store_client: object | None = None,
        reconciliation_report: ReconciliationReport | None = None,
        lifecycle_report: LifecycleReport | None = None,
    ) -> None:
        self.sqlite_db_path = Path(sqlite_db_path)
        self.config = load_platform_config() if config is None else config
        self.reference_now = reference_now
        self.checkpoint_path = None if checkpoint_path is None else Path(checkpoint_path)
        self.repository = repository
        self.lake_writer = lake_writer
        self.clickhouse_client = clickhouse_client
        self._object_store_client = object_store_client
        self.reconciliation_report = reconciliation_report
        self.lifecycle_report = lifecycle_report
        self._owned_closeables: list[object] = []

    def close(self) -> None:
        for resource in reversed(self._owned_closeables):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
        self._owned_closeables.clear()

    def run(self) -> PlatformAuditReport:
        self._ensure_runtime_dependencies()
        assert self.repository is not None
        assert self.lake_writer is not None
        assert self.clickhouse_client is not None

        cutover = summarize_cutover_state(self.config)
        reconciliation = self.reconciliation_report or run_reconciliation(
            self.sqlite_db_path,
            config=self.config,
            reference_now=self.reference_now,
            repository=self.repository,
            lake_writer=self.lake_writer,
            clickhouse_client=self.clickhouse_client,
        )
        current_state = self._build_current_state_path(cutover=cutover)
        analytical = self._build_analytical_path(cutover=cutover)
        lifecycle = self._build_lifecycle_path(cutover=cutover)
        backfill = self._build_backfill_path(cutover=cutover, reconciliation=reconciliation)
        overall_status = _build_overall_status(
            reconciliation=reconciliation,
            paths=(current_state, analytical, lifecycle, backfill),
        )
        return PlatformAuditReport(
            sqlite_db_path=str(self.sqlite_db_path),
            generated_at=_utc_now(),
            cutover=cutover,
            reconciliation=reconciliation,
            current_state=current_state,
            analytical=analytical,
            lifecycle=lifecycle,
            backfill=backfill,
            overall_status=overall_status,
        )

    def run_embedded_snapshot(self) -> dict[str, object]:
        cutover = summarize_cutover_state(self.config)
        if _embedded_audit_needs_runtime_dependencies(cutover):
            self._ensure_runtime_dependencies()

        current_state = self._build_current_state_path(cutover=cutover)
        analytical = self._build_analytical_path(cutover=cutover)
        lifecycle = self._build_lifecycle_path(cutover=cutover)
        backfill = self._build_backfill_path_without_reconciliation(cutover=cutover)
        note = _embedded_audit_note(self.sqlite_db_path)
        overall_status = _build_embedded_overall_status(
            paths=(current_state, analytical, lifecycle, backfill),
        )
        command = f"python -m vinted_radar.cli platform-audit --db {self.sqlite_db_path}"
        return {
            "sqlite_db_path": str(self.sqlite_db_path),
            "generated_at": _utc_now(),
            "cutover": cutover.as_dict(),
            "summary": {
                "reconciliation_status": "deferred",
                "current_state_status": current_state.status,
                "analytical_status": analytical.status,
                "lifecycle_status": lifecycle.status,
                "backfill_status": backfill.status,
            },
            "reconciliation": {
                "store": "reconciliation",
                "status": "deferred",
                "datasets": [],
                "command": command,
                "notes": [note],
            },
            "paths": {
                "current_state": current_state.as_dict(),
                "analytical": analytical.as_dict(),
                "lifecycle": lifecycle.as_dict(),
                "backfill": backfill.as_dict(),
            },
            "overall_status": overall_status,
            "ok": False,
            "error": None,
            "embedded": True,
            "notes": [note],
        }

    def _ensure_runtime_dependencies(self) -> None:
        if self.repository is None:
            self.repository = PostgresMutableTruthRepository.from_dsn(self.config.postgres.dsn)
            self._owned_closeables.append(self.repository)
        if self.lake_writer is None:
            self.lake_writer = ParquetLakeWriter.from_config(self.config, client=self._object_store_client)
            if self._object_store_client is None:
                self._owned_closeables.append(self.lake_writer.object_store.client)
        if self.clickhouse_client is None:
            self.clickhouse_client = _get_clickhouse_client(self.config, database=self.config.clickhouse.database)
            self._owned_closeables.append(self.clickhouse_client)

    def _build_current_state_path(self, *, cutover: CutoverStatusSnapshot) -> AuditPathStatus:
        command = f"python -m vinted_radar.cli platform-audit --db {self.sqlite_db_path}"
        if not _current_state_path_enabled(cutover):
            return _disabled_path(
                "current_state",
                command=command,
                detail="PostgreSQL current-state writes are disabled in the current cutover mode.",
            )
        checkpoint = self._checkpoint(consumer_name=POSTGRES_CURRENT_STATE_CONSUMER, sink=POSTGRES_CURRENT_STATE_SINK)
        return _path_from_checkpoint(path="current_state", checkpoint=checkpoint, command=command)

    def _build_analytical_path(self, *, cutover: CutoverStatusSnapshot) -> AuditPathStatus:
        command = (
            "python -m vinted_radar.cli clickhouse-ingest-status "
            f"--consumer-name {CLICKHOUSE_INGEST_CONSUMER}"
        )
        if not _analytical_path_enabled(cutover):
            return _disabled_path(
                "analytical",
                command=command,
                detail="ClickHouse analytical writes are disabled in the current cutover mode.",
            )
        checkpoint = self._checkpoint(consumer_name=CLICKHOUSE_INGEST_CONSUMER, sink=CLICKHOUSE_OUTBOX_SINK)
        return _path_from_checkpoint(path="analytical", checkpoint=checkpoint, command=command)

    def _build_lifecycle_path(self, *, cutover: CutoverStatusSnapshot) -> AuditPathStatus:
        command = "python -m vinted_radar.cli platform-lifecycle --dry-run"
        if not _platform_stack_enabled(cutover):
            return _disabled_path(
                "lifecycle",
                command=command,
                detail="Platform lifecycle controls are inactive while platform writes and reads stay on SQLite.",
            )
        try:
            report = self.lifecycle_report or run_lifecycle_jobs(
                config=self.config,
                apply=False,
                reference_now=self.reference_now,
                postgres_connection=getattr(self.repository, "connection", None),
                clickhouse_client=self.clickhouse_client,
                object_store_client=self._object_store_client_for_lifecycle(),
            )
        except Exception as exc:  # noqa: BLE001
            return AuditPathStatus(
                path="lifecycle",
                status="failed",
                detail=f"Lifecycle dry-run failed: {type(exc).__name__}: {exc}",
                command=command,
                last_error=f"{type(exc).__name__}: {exc}",
            )

        section_statuses = (
            report.clickhouse.status,
            report.postgres.status,
            report.object_storage.status,
        )
        if not report.ok:
            status = "failed"
        elif any(section in {"planned", "applied"} for section in section_statuses):
            status = "lagging"
        else:
            status = "healthy"
        detail = (
            "Dry-run posture: clickhouse {clickhouse}, postgres {postgres}, object-storage {object_storage}; "
            "pending archive rows {archived}, pending deletes {deleted}."
        ).format(
            clickhouse=report.clickhouse.status,
            postgres=report.postgres.status,
            object_storage=report.object_storage.status,
            archived=report.posture.archived_row_count,
            deleted=report.posture.deleted_row_count,
        )
        return AuditPathStatus(
            path="lifecycle",
            status=status,
            detail=detail,
            command=command,
            raw_status=status,
            updated_at=report.generated_at,
            metadata={
                "clickhouse_status": report.clickhouse.status,
                "postgres_status": report.postgres.status,
                "object_storage_status": report.object_storage.status,
                "pending_archive_rows": report.posture.archived_row_count,
                "pending_delete_rows": report.posture.deleted_row_count,
            },
        )

    def _build_backfill_path(
        self,
        *,
        cutover: CutoverStatusSnapshot,
        reconciliation: ReconciliationReport,
    ) -> AuditPathStatus:
        resolved_checkpoint = self.checkpoint_path or _default_full_backfill_checkpoint_path(self.sqlite_db_path)
        command = f"python -m vinted_radar.cli full-backfill --db {self.sqlite_db_path} --dry-run --checkpoint {resolved_checkpoint}"
        if not _platform_stack_enabled(cutover):
            return _disabled_path(
                "backfill",
                command=command,
                detail="Historical backfill audit is inactive while platform writes and reads stay on SQLite.",
            )
        if not resolved_checkpoint.exists():
            if reconciliation.ok and _object_storage_has_coverage(reconciliation):
                return AuditPathStatus(
                    path="backfill",
                    status="healthy",
                    detail="No local checkpoint file is present, but cross-store reconciliation still finds manifest-backed coverage across the platform stores.",
                    command=command,
                    metadata={
                        "checkpoint_path": str(resolved_checkpoint),
                        "checkpoint_present": False,
                    },
                )
            return AuditPathStatus(
                path="backfill",
                status="not-run",
                detail=f"No full-backfill checkpoint is present at {resolved_checkpoint}.",
                command=command,
                metadata={
                    "checkpoint_path": str(resolved_checkpoint),
                    "checkpoint_present": False,
                },
            )

        try:
            payload = json.loads(resolved_checkpoint.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("Checkpoint must decode to an object.")
        except Exception as exc:  # noqa: BLE001
            return AuditPathStatus(
                path="backfill",
                status="failed",
                detail=f"Backfill checkpoint inspection failed: {type(exc).__name__}: {exc}",
                command=command,
                last_error=f"{type(exc).__name__}: {exc}",
                metadata={
                    "checkpoint_path": str(resolved_checkpoint),
                    "checkpoint_present": True,
                },
            )

        dataset_state = dict(payload.get("datasets") or {})
        clickhouse_state = dict(payload.get("clickhouse") or {})
        completed = bool(payload.get("completed"))
        completed_batches = sum(int((state or {}).get("completed_batches") or 0) for state in dataset_state.values())
        processed_rows = int(clickhouse_state.get("processed_count") or 0)
        if completed:
            status = "complete" if reconciliation.ok else "lagging"
            detail = (
                f"Checkpoint completed with {completed_batches} batch(es) recorded and "
                f"ClickHouse worker progress {processed_rows} row(s)."
            )
        elif completed_batches or processed_rows:
            status = "in-progress"
            detail = (
                f"Checkpoint is still in progress with {completed_batches} completed batch(es) and "
                f"ClickHouse worker progress {processed_rows} row(s)."
            )
        else:
            status = "not-run"
            detail = "Checkpoint exists but does not record any completed backfill work yet."
        return AuditPathStatus(
            path="backfill",
            status=status,
            detail=detail,
            command=command,
            raw_status="completed" if completed else "incomplete",
            updated_at=_optional_str(payload.get("updated_at")),
            metadata={
                "checkpoint_path": str(resolved_checkpoint),
                "checkpoint_present": True,
                "completed": completed,
                "reference_now": _optional_str(payload.get("reference_now")),
                "completed_batches": completed_batches,
                "clickhouse_claimed_count": int(clickhouse_state.get("claimed_count") or 0),
                "clickhouse_processed_count": processed_rows,
                "clickhouse_skipped_count": int(clickhouse_state.get("skipped_count") or 0),
            },
        )

    def _build_backfill_path_without_reconciliation(self, *, cutover: CutoverStatusSnapshot) -> AuditPathStatus:
        resolved_checkpoint = self.checkpoint_path or _default_full_backfill_checkpoint_path(self.sqlite_db_path)
        command = f"python -m vinted_radar.cli full-backfill --db {self.sqlite_db_path} --dry-run --checkpoint {resolved_checkpoint}"
        if not _platform_stack_enabled(cutover):
            return _disabled_path(
                "backfill",
                command=command,
                detail="Historical backfill audit is inactive while platform writes and reads stay on SQLite.",
            )
        if not resolved_checkpoint.exists():
            return AuditPathStatus(
                path="backfill",
                status="not-run",
                detail=(
                    f"No full-backfill checkpoint is present at {resolved_checkpoint}. "
                    "Embedded audit skipped the cross-store coverage scan."
                ),
                command=command,
                metadata={
                    "checkpoint_path": str(resolved_checkpoint),
                    "checkpoint_present": False,
                    "reconciliation_deferred": True,
                },
            )

        try:
            payload = json.loads(resolved_checkpoint.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("Checkpoint must decode to an object.")
        except Exception as exc:  # noqa: BLE001
            return AuditPathStatus(
                path="backfill",
                status="failed",
                detail=f"Backfill checkpoint inspection failed: {type(exc).__name__}: {exc}",
                command=command,
                last_error=f"{type(exc).__name__}: {exc}",
                metadata={
                    "checkpoint_path": str(resolved_checkpoint),
                    "checkpoint_present": True,
                    "reconciliation_deferred": True,
                },
            )

        dataset_state = dict(payload.get("datasets") or {})
        clickhouse_state = dict(payload.get("clickhouse") or {})
        completed = bool(payload.get("completed"))
        completed_batches = sum(int((state or {}).get("completed_batches") or 0) for state in dataset_state.values())
        processed_rows = int(clickhouse_state.get("processed_count") or 0)
        if completed:
            status = "complete"
            detail = (
                f"Checkpoint completed with {completed_batches} batch(es) recorded and "
                f"ClickHouse worker progress {processed_rows} row(s). "
                "Embedded audit did not rerun cross-store reconciliation."
            )
        elif completed_batches or processed_rows:
            status = "in-progress"
            detail = (
                f"Checkpoint is still in progress with {completed_batches} completed batch(es) and "
                f"ClickHouse worker progress {processed_rows} row(s)."
            )
        else:
            status = "not-run"
            detail = "Checkpoint exists but does not record any completed backfill work yet."
        return AuditPathStatus(
            path="backfill",
            status=status,
            detail=detail,
            command=command,
            raw_status="completed" if completed else "incomplete",
            updated_at=_optional_str(payload.get("updated_at")),
            metadata={
                "checkpoint_path": str(resolved_checkpoint),
                "checkpoint_present": True,
                "completed": completed,
                "reference_now": _optional_str(payload.get("reference_now")),
                "completed_batches": completed_batches,
                "clickhouse_claimed_count": int(clickhouse_state.get("claimed_count") or 0),
                "clickhouse_processed_count": processed_rows,
                "clickhouse_skipped_count": int(clickhouse_state.get("skipped_count") or 0),
                "reconciliation_deferred": True,
            },
        )

    def _checkpoint(self, *, consumer_name: str, sink: str) -> dict[str, object] | None:
        resolver = getattr(self.repository, "outbox_checkpoint", None)
        if not callable(resolver):
            return None
        checkpoint = resolver(consumer_name=consumer_name, sink=sink)
        return None if checkpoint is None else dict(checkpoint)

    def _object_store_client_for_lifecycle(self) -> object | None:
        if self._object_store_client is not None:
            return self._object_store_client
        if self.lake_writer is None:
            return None
        return self.lake_writer.object_store.client


def run_platform_audit(
    sqlite_db_path: str | Path,
    *,
    config: PlatformConfig | None = None,
    reference_now: str | None = None,
    checkpoint_path: str | Path | None = None,
    repository: PostgresMutableTruthRepository | object | None = None,
    lake_writer: ParquetLakeWriter | None = None,
    clickhouse_client: object | None = None,
    object_store_client: object | None = None,
    reconciliation_report: ReconciliationReport | None = None,
    lifecycle_report: LifecycleReport | None = None,
) -> PlatformAuditReport:
    service = PlatformAuditService(
        sqlite_db_path,
        config=config,
        reference_now=reference_now,
        checkpoint_path=checkpoint_path,
        repository=repository,
        lake_writer=lake_writer,
        clickhouse_client=clickhouse_client,
        object_store_client=object_store_client,
        reconciliation_report=reconciliation_report,
        lifecycle_report=lifecycle_report,
    )
    try:
        return service.run()
    finally:
        service.close()


def load_platform_audit_snapshot(
    sqlite_db_path: str | Path,
    *,
    config: PlatformConfig | None = None,
    reference_now: str | None = None,
    checkpoint_path: str | Path | None = None,
    embedded: bool = False,
) -> dict[str, object]:
    resolved_config = config
    config_error: str | None = None
    if resolved_config is None:
        try:
            resolved_config = load_platform_config()
        except ValueError as exc:
            config_error = str(exc)

    cutover = summarize_cutover_state(resolved_config, config_error=config_error)
    try:
        if embedded:
            service = PlatformAuditService(
                sqlite_db_path,
                config=resolved_config,
                reference_now=reference_now,
                checkpoint_path=checkpoint_path,
            )
            try:
                return service.run_embedded_snapshot()
            finally:
                service.close()
        report = run_platform_audit(
            sqlite_db_path,
            config=resolved_config,
            reference_now=reference_now,
            checkpoint_path=checkpoint_path,
        )
        return report.as_dict()
    except Exception as exc:  # noqa: BLE001
        return {
            "sqlite_db_path": str(sqlite_db_path),
            "generated_at": _utc_now(),
            "cutover": cutover.as_dict(),
            "summary": {
                "reconciliation_status": "failed",
                "current_state_status": "failed",
                "analytical_status": "failed",
                "lifecycle_status": "failed",
                "backfill_status": "failed",
            },
            "reconciliation": None,
            "paths": {
                key: AuditPathStatus(
                    path=key,
                    status="failed",
                    detail=f"Platform audit failed: {type(exc).__name__}: {exc}",
                    command=f"python -m vinted_radar.cli platform-audit --db {sqlite_db_path}",
                    last_error=f"{type(exc).__name__}: {exc}",
                ).as_dict()
                for key in ("current_state", "analytical", "lifecycle", "backfill")
            },
            "overall_status": "failed",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "embedded": embedded,
        }


def _path_from_checkpoint(
    *,
    path: str,
    checkpoint: Mapping[str, object] | None,
    command: str,
) -> AuditPathStatus:
    if checkpoint is None:
        return AuditPathStatus(
            path=path,
            status="never-run",
            detail="No persisted outbox checkpoint is recorded yet.",
            command=command,
            raw_status="never-run",
        )

    raw_status = str(checkpoint.get("status") or "idle")
    status = {
        "idle": "healthy",
        "running": "active",
        "lagging": "lagging",
        "failed": "failed",
        "never-run": "never-run",
    }.get(raw_status, raw_status)
    lag_seconds = None if checkpoint.get("lag_seconds") is None else float(checkpoint.get("lag_seconds") or 0.0)
    detail = (
        "Checkpoint {raw_status}; last event {event}; last manifest {manifest}; lag {lag}."
    ).format(
        raw_status=raw_status,
        event=checkpoint.get("last_event_id") or "n/a",
        manifest=checkpoint.get("last_manifest_id") or "n/a",
        lag=_format_duration(lag_seconds),
    )
    last_error = _optional_str(checkpoint.get("last_error"))
    if last_error:
        detail += f" Last error: {last_error}."
    return AuditPathStatus(
        path=path,
        status=status,
        detail=detail,
        command=command,
        raw_status=raw_status,
        updated_at=_optional_str(checkpoint.get("updated_at")),
        lag_seconds=lag_seconds,
        last_error=last_error,
        metadata=dict(checkpoint.get("metadata") or {}),
    )


def _disabled_path(path: str, *, command: str, detail: str) -> AuditPathStatus:
    return AuditPathStatus(
        path=path,
        status="disabled",
        detail=detail,
        command=command,
        raw_status="disabled",
    )


def _build_overall_status(
    *,
    reconciliation: ReconciliationReport,
    paths: tuple[AuditPathStatus, ...],
) -> str:
    if any(path.status == "failed" for path in paths):
        return "failed"
    if not reconciliation.ok:
        return "lagging"
    if any(path.status in _ATTENTION_PATH_STATUSES for path in paths):
        return "lagging"
    return "healthy"


def _build_embedded_overall_status(*, paths: tuple[AuditPathStatus, ...]) -> str:
    if any(path.status == "failed" for path in paths):
        return "failed"
    if any(path.status in _ATTENTION_PATH_STATUSES for path in paths):
        return "lagging"
    return "healthy"


def _embedded_audit_needs_runtime_dependencies(cutover: CutoverStatusSnapshot) -> bool:
    return any(
        (
            _current_state_path_enabled(cutover),
            _analytical_path_enabled(cutover),
            _platform_stack_enabled(cutover),
        )
    )


def _embedded_audit_note(sqlite_db_path: str | Path) -> str:
    return (
        "Embedded platform audit skipped full cross-store reconciliation to keep runtime and health surfaces bounded. "
        f"Run `python -m vinted_radar.cli platform-audit --db {sqlite_db_path}` for the authoritative parity report."
    )


def _current_state_path_enabled(cutover: CutoverStatusSnapshot) -> bool:
    return cutover.postgres_writes_enabled or cutover.read_path == "polyglot-platform"


def _analytical_path_enabled(cutover: CutoverStatusSnapshot) -> bool:
    return cutover.clickhouse_writes_enabled or cutover.read_path == "polyglot-platform"


def _platform_stack_enabled(cutover: CutoverStatusSnapshot) -> bool:
    return cutover.platform_writes_enabled or cutover.polyglot_reads_enabled


def _object_storage_has_coverage(reconciliation: ReconciliationReport) -> bool:
    return any((dataset.actual.batch_count or 0) > 0 for dataset in reconciliation.object_storage.datasets)


def _default_full_backfill_checkpoint_path(sqlite_db_path: Path) -> Path:
    return sqlite_db_path.with_name(f"{sqlite_db_path.name}.full-backfill-checkpoint.json")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _format_duration(value: float | None) -> str:
    if value is None:
        return "n/a"
    seconds = max(int(round(float(value))), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _get_clickhouse_client(config: PlatformConfig, *, database: str):
    import clickhouse_connect

    parts = urlsplit(config.clickhouse.url)
    return clickhouse_connect.get_client(
        host=parts.hostname or "127.0.0.1",
        port=parts.port or (8443 if parts.scheme == "https" else 8123),
        username=config.clickhouse.username,
        password=config.clickhouse.password,
        database=database,
        secure=parts.scheme == "https",
    )


__all__ = [
    "AuditPathStatus",
    "PlatformAuditReport",
    "PlatformAuditService",
    "load_platform_audit_snapshot",
    "run_platform_audit",
]
