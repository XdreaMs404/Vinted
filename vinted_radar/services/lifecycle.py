from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from vinted_radar.platform.clickhouse_schema import (
    CLICKHOUSE_FACT_TABLE_CONTRACTS,
    CLICKHOUSE_ROLLUP_TABLE_CONTRACTS,
)
from vinted_radar.platform.config import PlatformConfig, load_platform_config, redact_url_credentials
from vinted_radar.platform.object_store import S3ObjectStore

_CLICKHOUSE_TTL_COLUMN_BY_TABLE = {
    "fact_listing_seen_events": "observed_at",
    "fact_listing_probe_events": "probed_at",
    "fact_listing_change_events": "occurred_at",
    "rollup_listing_seen_hourly": "bucket_start",
    "rollup_listing_seen_daily": "bucket_date",
    "rollup_category_daily": "bucket_date",
    "rollup_brand_daily": "bucket_date",
}


@dataclass(frozen=True, slots=True)
class ClickHouseTTLAction:
    table: str
    ttl_column: str
    ttl_days: int
    statement: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "table": self.table,
            "ttl_column": self.ttl_column,
            "ttl_days": self.ttl_days,
            "statement": self.statement,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ClickHouseLifecycleSection:
    status: str
    database: str
    actions: tuple[ClickHouseTTLAction, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "database": self.database,
            "actions": [action.as_dict() for action in self.actions],
        }


@dataclass(frozen=True, slots=True)
class PostgresLifecycleAction:
    table: str
    key_column: str
    retention_days: int
    cutoff: str
    matched_rows: int
    archived_rows: int
    deleted_rows: int
    archive_key: str | None
    protected_rows: int
    status: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "table": self.table,
            "key_column": self.key_column,
            "retention_days": self.retention_days,
            "cutoff": self.cutoff,
            "matched_rows": self.matched_rows,
            "archived_rows": self.archived_rows,
            "deleted_rows": self.deleted_rows,
            "archive_key": self.archive_key,
            "protected_rows": self.protected_rows,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PostgresLifecycleSection:
    status: str
    actions: tuple[PostgresLifecycleAction, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "actions": [action.as_dict() for action in self.actions],
        }


@dataclass(frozen=True, slots=True)
class ObjectStorageLifecycleRuleStatus:
    prefix_name: str
    prefix: str
    retention_class: str
    retention_days: int
    object_count: int
    rule_id: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "prefix_name": self.prefix_name,
            "prefix": self.prefix,
            "retention_class": self.retention_class,
            "retention_days": self.retention_days,
            "object_count": self.object_count,
            "rule_id": self.rule_id,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ObjectStorageLifecycleSection:
    status: str
    bucket: str
    rules: tuple[ObjectStorageLifecycleRuleStatus, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "bucket": self.bucket,
            "rules": [rule.as_dict() for rule in self.rules],
        }


@dataclass(frozen=True, slots=True)
class StoragePostureSummary:
    bounded: bool
    clickhouse_ttl_table_count: int
    postgres_prune_target_count: int
    object_storage_rule_count: int
    archived_row_count: int
    deleted_row_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "bounded": self.bounded,
            "clickhouse_ttl_table_count": self.clickhouse_ttl_table_count,
            "postgres_prune_target_count": self.postgres_prune_target_count,
            "object_storage_rule_count": self.object_storage_rule_count,
            "archived_row_count": self.archived_row_count,
            "deleted_row_count": self.deleted_row_count,
        }


@dataclass(frozen=True, slots=True)
class LifecycleReport:
    generated_at: str
    apply: bool
    postgres_dsn: str
    clickhouse_url: str
    clickhouse_database: str
    object_store_bucket: str
    clickhouse: ClickHouseLifecycleSection
    postgres: PostgresLifecycleSection
    object_storage: ObjectStorageLifecycleSection
    posture: StoragePostureSummary

    @property
    def ok(self) -> bool:
        return all(
            section.status != "failed"
            for section in (self.clickhouse, self.postgres, self.object_storage)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "apply": self.apply,
            "postgres_dsn": redact_url_credentials(self.postgres_dsn),
            "clickhouse_url": self.clickhouse_url,
            "clickhouse_database": self.clickhouse_database,
            "object_store_bucket": self.object_store_bucket,
            "clickhouse": self.clickhouse.as_dict(),
            "postgres": self.postgres.as_dict(),
            "object_storage": self.object_storage.as_dict(),
            "posture": self.posture.as_dict(),
            "ok": self.ok,
        }


class LifecycleService:
    def __init__(
        self,
        *,
        config: PlatformConfig | None = None,
        apply: bool = True,
        reference_now: str | None = None,
        postgres_connection: object | None = None,
        clickhouse_client: object | None = None,
        object_store_client: object | None = None,
    ) -> None:
        self.config = load_platform_config() if config is None else config
        self.apply = apply
        self.reference_now = reference_now
        self.postgres_connection = postgres_connection
        self.clickhouse_client = clickhouse_client
        self.object_store_client = object_store_client
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

    def run(self) -> LifecycleReport:
        now = _resolve_now(self.reference_now)
        self._ensure_runtime_dependencies()
        assert self.postgres_connection is not None
        assert self.clickhouse_client is not None
        assert self.object_store_client is not None

        clickhouse = self._run_clickhouse_ttl_jobs()
        postgres = self._run_postgres_jobs(now)
        object_storage = self._run_object_storage_jobs()
        posture = StoragePostureSummary(
            bounded=all(section.status != "failed" for section in (clickhouse, postgres, object_storage)),
            clickhouse_ttl_table_count=len(clickhouse.actions),
            postgres_prune_target_count=len(postgres.actions),
            object_storage_rule_count=len(object_storage.rules),
            archived_row_count=sum(action.archived_rows for action in postgres.actions),
            deleted_row_count=sum(action.deleted_rows for action in postgres.actions),
        )
        return LifecycleReport(
            generated_at=now.isoformat(),
            apply=self.apply,
            postgres_dsn=self.config.postgres.dsn,
            clickhouse_url=self.config.clickhouse.url,
            clickhouse_database=self.config.clickhouse.database,
            object_store_bucket=self.config.object_storage.bucket,
            clickhouse=clickhouse,
            postgres=postgres,
            object_storage=object_storage,
            posture=posture,
        )

    def _ensure_runtime_dependencies(self) -> None:
        if self.postgres_connection is None:
            self.postgres_connection = _connect_postgres(self.config.postgres.dsn)
            self._owned_closeables.append(self.postgres_connection)
        if self.clickhouse_client is None:
            self.clickhouse_client = _get_clickhouse_client(self.config, database=self.config.clickhouse.database)
            self._owned_closeables.append(self.clickhouse_client)
        if self.object_store_client is None:
            object_store = S3ObjectStore.from_config(self.config)
            self.object_store_client = object_store.client
            self._owned_closeables.append(self.object_store_client)

    def _run_clickhouse_ttl_jobs(self) -> ClickHouseLifecycleSection:
        actions: list[ClickHouseTTLAction] = []
        status = "ok"
        contracts = tuple(CLICKHOUSE_FACT_TABLE_CONTRACTS) + tuple(CLICKHOUSE_ROLLUP_TABLE_CONTRACTS)
        for contract in contracts:
            if contract.ttl_days is None:
                continue
            ttl_column = _CLICKHOUSE_TTL_COLUMN_BY_TABLE[contract.name]
            statement = (
                f"ALTER TABLE {self.config.clickhouse.database}.{contract.name} "
                f"MODIFY TTL {ttl_column} + INTERVAL {contract.ttl_days} DAY"
            )
            try:
                if self.apply:
                    assert self.clickhouse_client is not None
                    self.clickhouse_client.command(statement)
                action_status = "applied" if self.apply else "planned"
                actions.append(
                    ClickHouseTTLAction(
                        table=contract.name,
                        ttl_column=ttl_column,
                        ttl_days=contract.ttl_days,
                        statement=statement,
                        status=action_status,
                        detail=(
                            f"TTL {ttl_column} + INTERVAL {contract.ttl_days} DAY enforced"
                            if self.apply
                            else f"TTL {ttl_column} + INTERVAL {contract.ttl_days} DAY ready to apply"
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                actions.append(
                    ClickHouseTTLAction(
                        table=contract.name,
                        ttl_column=ttl_column,
                        ttl_days=contract.ttl_days,
                        statement=statement,
                        status="failed",
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
        return ClickHouseLifecycleSection(
            status=_section_status(status, actions),
            database=self.config.clickhouse.database,
            actions=tuple(actions),
        )

    def _run_postgres_jobs(self, now: datetime) -> PostgresLifecycleSection:
        actions: list[PostgresLifecycleAction] = []
        specs = (
            {
                "table": "platform_bootstrap_audit",
                "archive_slug": "bootstrap-audit",
                "key_column": "event_id",
                "retention_days": self.config.lifecycle.postgres.bootstrap_audit_retention_days,
                "cutoff_column": "recorded_at",
                "columns": ("event_id", "component", "status", "detail", "recorded_at"),
                "where": "recorded_at < %s",
                "params": lambda cutoff: (cutoff.isoformat(),),
                "protected_ids": lambda connection: set(),
            },
            {
                "table": "platform_outbox",
                "archive_slug": "outbox-delivered",
                "key_column": "outbox_id",
                "retention_days": self.config.lifecycle.postgres.delivered_outbox_retention_days,
                "cutoff_column": "delivered_at",
                "columns": (
                    "outbox_id",
                    "event_id",
                    "sink",
                    "status",
                    "available_at",
                    "claimed_at",
                    "claimed_by",
                    "locked_until",
                    "attempt_count",
                    "last_attempt_at",
                    "delivered_at",
                    "last_error",
                    "manifest_id",
                    "created_at",
                ),
                "where": "status = 'delivered' AND delivered_at IS NOT NULL AND delivered_at < %s",
                "params": lambda cutoff: (cutoff.isoformat(),),
                "protected_ids": lambda connection: set(),
            },
            {
                "table": "platform_outbox",
                "archive_slug": "outbox-failed",
                "key_column": "outbox_id",
                "retention_days": self.config.lifecycle.postgres.failed_outbox_retention_days,
                "cutoff_column": "last_attempt_at",
                "columns": (
                    "outbox_id",
                    "event_id",
                    "sink",
                    "status",
                    "available_at",
                    "claimed_at",
                    "claimed_by",
                    "locked_until",
                    "attempt_count",
                    "last_attempt_at",
                    "delivered_at",
                    "last_error",
                    "manifest_id",
                    "created_at",
                ),
                "where": "status = 'failed' AND COALESCE(last_attempt_at, created_at) < %s",
                "params": lambda cutoff: (cutoff.isoformat(),),
                "protected_ids": lambda connection: set(),
            },
            {
                "table": "platform_runtime_cycles",
                "archive_slug": "runtime-cycles",
                "key_column": "cycle_id",
                "retention_days": self.config.lifecycle.postgres.runtime_cycles_retention_days,
                "cutoff_column": "finished_at",
                "columns": (
                    "cycle_id",
                    "started_at",
                    "finished_at",
                    "mode",
                    "status",
                    "phase",
                    "interval_seconds",
                    "state_probe_limit",
                    "discovery_run_id",
                    "state_probed_count",
                    "tracked_listings",
                    "first_pass_only",
                    "fresh_followup",
                    "aging_followup",
                    "stale_followup",
                    "last_error",
                    "state_refresh_summary_json",
                    "config_json",
                    "last_event_id",
                    "last_manifest_id",
                    "projected_at",
                ),
                "where": "finished_at IS NOT NULL AND finished_at < %s",
                "params": lambda cutoff: (cutoff.isoformat(),),
                "protected_ids": _protected_runtime_cycle_ids,
            },
        )

        section_status = "ok"
        for spec in specs:
            cutoff = now - timedelta(days=int(spec["retention_days"]))
            try:
                rows = _fetch_rows(
                    self.postgres_connection,
                    table_name=str(spec["table"]),
                    columns=tuple(spec["columns"]),
                    where=str(spec["where"]),
                    params=tuple(spec["params"](cutoff)),
                    order_by=f"{spec['cutoff_column']} ASC, {spec['key_column']} ASC",
                )
                protected_ids = set(spec["protected_ids"](self.postgres_connection))
                prunable_rows = [row for row in rows if row.get(str(spec["key_column"])) not in protected_ids]
                archive_key = None
                deleted_rows = 0
                if self.apply and prunable_rows:
                    archive_key = self._archive_rows(
                        str(spec["archive_slug"]),
                        table_name=str(spec["table"]),
                        cutoff=cutoff,
                        now=now,
                        rows=prunable_rows,
                    )
                    _delete_rows(
                        self.postgres_connection,
                        table_name=str(spec["table"]),
                        key_column=str(spec["key_column"]),
                        ids=[row[str(spec["key_column"])] for row in prunable_rows],
                    )
                    commit = getattr(self.postgres_connection, "commit", None)
                    if callable(commit):
                        commit()
                    deleted_rows = len(prunable_rows)
                action_status = "applied" if self.apply else "planned"
                if not prunable_rows:
                    action_status = "ok"
                actions.append(
                    PostgresLifecycleAction(
                        table=str(spec["table"]),
                        key_column=str(spec["key_column"]),
                        retention_days=int(spec["retention_days"]),
                        cutoff=cutoff.isoformat(),
                        matched_rows=len(rows),
                        archived_rows=len(prunable_rows) if self.apply else 0,
                        deleted_rows=deleted_rows,
                        archive_key=archive_key,
                        protected_rows=len(rows) - len(prunable_rows),
                        status=action_status,
                        detail=_describe_postgres_action(
                            table=str(spec["table"]),
                            matched_rows=len(rows),
                            prunable_rows=len(prunable_rows),
                            protected_rows=len(rows) - len(prunable_rows),
                            apply=self.apply,
                            archive_key=archive_key,
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                rollback = getattr(self.postgres_connection, "rollback", None)
                if callable(rollback):
                    rollback()
                section_status = "failed"
                actions.append(
                    PostgresLifecycleAction(
                        table=str(spec["table"]),
                        key_column=str(spec["key_column"]),
                        retention_days=int(spec["retention_days"]),
                        cutoff=cutoff.isoformat(),
                        matched_rows=0,
                        archived_rows=0,
                        deleted_rows=0,
                        archive_key=None,
                        protected_rows=0,
                        status="failed",
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
        return PostgresLifecycleSection(status=_section_status(section_status, actions), actions=tuple(actions))

    def _archive_rows(
        self,
        archive_slug: str,
        *,
        table_name: str,
        cutoff: datetime,
        now: datetime,
        rows: Sequence[Mapping[str, object]],
    ) -> str:
        object_store = S3ObjectStore.from_config(self.config.object_storage, client=self.object_store_client)
        archive_key = (
            f"{self.config.storage.archives}/postgres/{table_name}/"
            f"{archive_slug}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        payload = {
            "table": table_name,
            "archived_at": now.isoformat(),
            "cutoff": cutoff.isoformat(),
            "row_count": len(rows),
            "rows": [_normalize_json_row(row) for row in rows],
        }
        object_store.put_json(key=archive_key, payload=payload, overwrite=True)
        return archive_key

    def _run_object_storage_jobs(self) -> ObjectStorageLifecycleSection:
        object_store = S3ObjectStore.from_config(self.config.object_storage, client=self.object_store_client)
        getter = getattr(object_store.client, "get_bucket_lifecycle_configuration", None)
        putter = getattr(object_store.client, "put_bucket_lifecycle_configuration", None)
        if not callable(getter) or not callable(putter):
            return ObjectStorageLifecycleSection(
                status="failed",
                bucket=self.config.object_storage.bucket,
                rules=(),
            )

        desired_rules = tuple(_desired_bucket_rules(self.config))
        try:
            current_rules = _load_bucket_rules(object_store.client, self.config.object_storage.bucket)
            current_by_id = {rule["ID"]: rule for rule in current_rules}
            desired_by_id = {rule["ID"]: rule for rule in desired_rules}
            changed = current_by_id != desired_by_id
            if self.apply and changed:
                putter(
                    Bucket=self.config.object_storage.bucket,
                    LifecycleConfiguration={"Rules": list(desired_rules)},
                )
            statuses: list[ObjectStorageLifecycleRuleStatus] = []
            for prefix_name, prefix, retention_policy in _iter_object_storage_policies(self.config):
                rule_id = _rule_id(prefix_name)
                object_count = len(object_store.list_keys(prefix))
                if changed and self.apply:
                    status = "applied"
                    detail = f"Lifecycle rule {rule_id} set on prefix {prefix}"
                elif changed:
                    status = "planned"
                    detail = f"Lifecycle rule {rule_id} will be set on prefix {prefix}"
                else:
                    status = "ok"
                    detail = f"Lifecycle rule {rule_id} already matches prefix {prefix}"
                statuses.append(
                    ObjectStorageLifecycleRuleStatus(
                        prefix_name=prefix_name,
                        prefix=prefix,
                        retention_class=retention_policy.retention_class,
                        retention_days=retention_policy.retention_days,
                        object_count=object_count,
                        rule_id=rule_id,
                        status=status,
                        detail=detail,
                    )
                )
            return ObjectStorageLifecycleSection(
                status=_section_status("ok", statuses),
                bucket=self.config.object_storage.bucket,
                rules=tuple(statuses),
            )
        except Exception:
            raise


def run_lifecycle_jobs(
    *,
    config: PlatformConfig | None = None,
    apply: bool = True,
    reference_now: str | None = None,
    postgres_connection: object | None = None,
    clickhouse_client: object | None = None,
    object_store_client: object | None = None,
) -> LifecycleReport:
    service = LifecycleService(
        config=config,
        apply=apply,
        reference_now=reference_now,
        postgres_connection=postgres_connection,
        clickhouse_client=clickhouse_client,
        object_store_client=object_store_client,
    )
    try:
        return service.run()
    finally:
        service.close()


def _describe_postgres_action(
    *,
    table: str,
    matched_rows: int,
    prunable_rows: int,
    protected_rows: int,
    apply: bool,
    archive_key: str | None,
) -> str:
    if matched_rows == 0:
        return f"No rows exceeded retention in {table}"
    if not apply:
        return f"{prunable_rows} row(s) exceed retention in {table}; {protected_rows} protected"
    return (
        f"Archived and deleted {prunable_rows} row(s) from {table}"
        + ("" if protected_rows == 0 else f"; protected {protected_rows}")
        + ("" if archive_key is None else f"; archive {archive_key}")
    )


def _fetch_rows(
    connection: object,
    *,
    table_name: str,
    columns: Sequence[str],
    where: str,
    params: Sequence[object],
    order_by: str,
) -> list[dict[str, object]]:
    sql = f"SELECT {', '.join(columns)} FROM {table_name} WHERE {where} ORDER BY {order_by}"
    cursor = connection.execute(sql, tuple(params))
    rows = cursor.fetchall()
    return [_row_to_dict(columns, row) for row in rows]


def _row_to_dict(columns: Sequence[str], row: object) -> dict[str, object]:
    if isinstance(row, Mapping):
        return {column: _normalize_value(row.get(column)) for column in columns}
    mapping = getattr(row, "_mapping", None)
    if isinstance(mapping, Mapping):
        return {column: _normalize_value(mapping.get(column)) for column in columns}
    return {
        column: _normalize_value(row[index] if isinstance(row, Sequence) and index < len(row) else None)
        for index, column in enumerate(columns)
    }


def _delete_rows(connection: object, *, table_name: str, key_column: str, ids: Sequence[object]) -> None:
    if not ids:
        return
    placeholders = ", ".join(["%s"] * len(ids))
    connection.execute(
        f"DELETE FROM {table_name} WHERE {key_column} IN ({placeholders})",
        tuple(ids),
    )


def _protected_runtime_cycle_ids(connection: object) -> set[object]:
    cursor = connection.execute(
        "SELECT active_cycle_id, latest_cycle_id FROM platform_runtime_controller_state WHERE controller_id = %s",
        (1,),
    )
    row = cursor.fetchone()
    if row is None:
        return set()
    if isinstance(row, Mapping):
        values = {row.get("active_cycle_id"), row.get("latest_cycle_id")}
    else:
        mapping = getattr(row, "_mapping", None)
        if isinstance(mapping, Mapping):
            values = {mapping.get("active_cycle_id"), mapping.get("latest_cycle_id")}
        else:
            values = {row[0] if isinstance(row, Sequence) and len(row) >= 1 else None, row[1] if isinstance(row, Sequence) and len(row) >= 2 else None}
    return {value for value in values if value is not None}


def _desired_bucket_rules(config: PlatformConfig) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    for prefix_name, prefix, retention_policy in _iter_object_storage_policies(config):
        rules.append(
            {
                "ID": _rule_id(prefix_name),
                "Status": "Enabled",
                "Filter": {"Prefix": f"{prefix.rstrip('/')}/"},
                "Expiration": {"Days": retention_policy.retention_days},
            }
        )
    return rules


def _iter_object_storage_policies(config: PlatformConfig):
    yield "raw_events", config.storage.raw_events, config.lifecycle.object_storage.raw_events
    yield "manifests", config.storage.manifests, config.lifecycle.object_storage.manifests
    yield "parquet", config.storage.parquet, config.lifecycle.object_storage.parquet
    yield "archives", config.storage.archives, config.lifecycle.object_storage.archives


def _load_bucket_rules(client: object, bucket: str) -> tuple[dict[str, object], ...]:
    try:
        response = client.get_bucket_lifecycle_configuration(Bucket=bucket)
    except Exception as exc:  # noqa: BLE001
        code = _error_code(exc)
        if code in {"404", "NotFound", "NoSuchLifecycleConfiguration", "NoSuchBucket"}:
            return ()
        raise
    raw_rules = response.get("Rules") if isinstance(response, Mapping) else None
    if not isinstance(raw_rules, list):
        return ()
    normalized: list[dict[str, object]] = []
    for rule in raw_rules:
        if not isinstance(rule, Mapping):
            continue
        prefix = rule.get("Filter", {}).get("Prefix") if isinstance(rule.get("Filter"), Mapping) else None
        expiration = rule.get("Expiration") if isinstance(rule.get("Expiration"), Mapping) else {}
        normalized.append(
            {
                "ID": str(rule.get("ID") or ""),
                "Status": str(rule.get("Status") or "Enabled"),
                "Filter": {"Prefix": str(prefix or "")},
                "Expiration": {"Days": int(expiration.get("Days") or 0)},
            }
        )
    normalized.sort(key=lambda item: str(item.get("ID") or ""))
    return tuple(normalized)


def _rule_id(prefix_name: str) -> str:
    return prefix_name.replace("_", "-") + "-retention"


def _section_status(base_status: str, actions: Sequence[object]) -> str:
    if base_status == "failed":
        return "failed"
    statuses = {str(getattr(action, "status", "ok")) for action in actions}
    if "failed" in statuses:
        return "failed"
    if "applied" in statuses:
        return "applied"
    if "planned" in statuses:
        return "planned"
    return "ok"


def _normalize_json_row(row: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _normalize_value(value) for key, value in row.items()}


def _normalize_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item) for item in value]
    return str(value)


def _resolve_now(reference_now: str | None) -> datetime:
    if reference_now is None:
        return datetime.now(UTC)
    normalized = reference_now.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _connect_postgres(dsn: str):
    import psycopg

    return psycopg.connect(dsn)


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


def _error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return None if code is None else str(code)


__all__ = [
    "ClickHouseLifecycleSection",
    "ClickHouseTTLAction",
    "LifecycleReport",
    "LifecycleService",
    "ObjectStorageLifecycleRuleStatus",
    "ObjectStorageLifecycleSection",
    "PostgresLifecycleAction",
    "PostgresLifecycleSection",
    "StoragePostureSummary",
    "run_lifecycle_jobs",
]
