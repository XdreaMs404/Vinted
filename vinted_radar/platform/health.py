from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlatformHealthSnapshot:
    mode: str
    ok: bool
    check_writes: bool
    postgres_ok: bool
    clickhouse_ok: bool
    object_storage_ok: bool
    postgres_detail: str
    clickhouse_detail: str
    object_storage_detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "check_writes": self.check_writes,
            "postgres_ok": self.postgres_ok,
            "clickhouse_ok": self.clickhouse_ok,
            "object_storage_ok": self.object_storage_ok,
            "postgres_detail": self.postgres_detail,
            "clickhouse_detail": self.clickhouse_detail,
            "object_storage_detail": self.object_storage_detail,
        }


@dataclass(frozen=True, slots=True)
class CutoverStatusSnapshot:
    mode: str
    dual_write_active: bool
    platform_writes_enabled: bool
    polyglot_reads_enabled: bool
    read_path: str
    write_targets: tuple[str, ...]
    platform_write_targets: tuple[str, ...]
    postgres_writes_enabled: bool
    clickhouse_writes_enabled: bool
    object_storage_writes_enabled: bool
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "dual_write_active": self.dual_write_active,
            "platform_writes_enabled": self.platform_writes_enabled,
            "polyglot_reads_enabled": self.polyglot_reads_enabled,
            "read_path": self.read_path,
            "write_targets": list(self.write_targets),
            "platform_write_targets": list(self.platform_write_targets),
            "postgres_writes_enabled": self.postgres_writes_enabled,
            "clickhouse_writes_enabled": self.clickhouse_writes_enabled,
            "object_storage_writes_enabled": self.object_storage_writes_enabled,
            "warnings": list(self.warnings),
        }


def summarize_platform_health(report: object) -> PlatformHealthSnapshot:
    postgres = getattr(report, "postgres")
    clickhouse = getattr(report, "clickhouse")
    object_storage = getattr(report, "object_storage")
    return PlatformHealthSnapshot(
        mode=str(getattr(report, "mode", "unknown")),
        ok=bool(getattr(report, "ok", False)),
        check_writes=bool(getattr(report, "check_writes", False)),
        postgres_ok=bool(getattr(postgres, "ok", False)),
        clickhouse_ok=bool(getattr(clickhouse, "ok", False)),
        object_storage_ok=bool(getattr(object_storage, "ok", False)),
        postgres_detail=str(getattr(postgres, "detail", "n/a")),
        clickhouse_detail=str(getattr(clickhouse, "detail", "n/a")),
        object_storage_detail=str(getattr(object_storage, "detail", "n/a")),
    )


def summarize_cutover_state(config: object | None, *, config_error: str | None = None) -> CutoverStatusSnapshot:
    postgres_writes = _cutover_flag(config, "enable_postgres_writes")
    clickhouse_writes = _cutover_flag(config, "enable_clickhouse_writes")
    object_storage_writes = _cutover_flag(config, "enable_object_storage_writes")
    polyglot_reads = _cutover_flag(config, "enable_polyglot_reads")

    platform_write_targets = tuple(
        target
        for target, enabled in (
            ("postgres", postgres_writes),
            ("clickhouse", clickhouse_writes),
            ("object-storage", object_storage_writes),
        )
        if enabled
    )
    platform_writes_enabled = bool(platform_write_targets)
    dual_write_active = platform_writes_enabled
    write_targets = ("sqlite",) + platform_write_targets
    read_path = "polyglot-platform" if polyglot_reads else "sqlite"

    warnings: list[str] = []
    if config_error:
        warnings.append(f"Platform config error: {config_error}")
    if clickhouse_writes and not postgres_writes:
        warnings.append(
            "ClickHouse writes are enabled without PostgreSQL writes; the collector publisher only emits ClickHouse sink traffic when PostgreSQL outbox writes are enabled."
        )
    if polyglot_reads and not platform_writes_enabled:
        warnings.append(
            "Polyglot reads are enabled while platform writes are disabled; platform-backed reads may observe stale or empty data."
        )
    if platform_writes_enabled and not object_storage_writes:
        warnings.append(
            "Platform writes are enabled without object-storage evidence; new batches will not emit replay/audit manifests."
        )

    if config_error:
        mode = "config-error"
    elif not platform_writes_enabled and not polyglot_reads:
        mode = "sqlite-primary"
    elif platform_writes_enabled and not polyglot_reads:
        mode = "dual-write-shadow"
    elif platform_writes_enabled and polyglot_reads:
        mode = "polyglot-cutover"
    else:
        mode = "read-cutover-without-platform-writes"

    return CutoverStatusSnapshot(
        mode=mode,
        dual_write_active=dual_write_active,
        platform_writes_enabled=platform_writes_enabled,
        polyglot_reads_enabled=polyglot_reads,
        read_path=read_path,
        write_targets=write_targets,
        platform_write_targets=platform_write_targets,
        postgres_writes_enabled=postgres_writes,
        clickhouse_writes_enabled=clickhouse_writes,
        object_storage_writes_enabled=object_storage_writes,
        warnings=tuple(warnings),
    )


def render_platform_report_text(report: object) -> str:
    return "\n".join(render_platform_report_lines(report))


def render_platform_report_lines(report: object) -> tuple[str, ...]:
    config = dict(getattr(report, "config") or {})
    cutover = summarize_cutover_state(config)
    lines: list[str] = []
    lines.append(f"Mode: {getattr(report, 'mode', 'unknown')}")
    lines.append("Config snapshot:")
    lines.append(f"- Postgres: {dict(config.get('postgres') or {}).get('dsn') or 'n/a'}")
    lines.append(
        "- ClickHouse: {url} / {database}".format(
            url=dict(config.get("clickhouse") or {}).get("url") or "n/a",
            database=dict(config.get("clickhouse") or {}).get("database") or "n/a",
        )
    )
    lines.append(
        "- Object storage: {endpoint} / bucket {bucket}".format(
            endpoint=dict(config.get("object_storage") or {}).get("endpoint_url") or "n/a",
            bucket=dict(config.get("object_storage") or {}).get("bucket") or "n/a",
        )
    )
    lines.append(f"- Check writes: {'yes' if getattr(report, 'check_writes', False) else 'no'}")
    lines.extend(_render_cutover_lines(cutover))
    lines.extend(_render_platform_system_lines("PostgreSQL", getattr(report, "postgres", None)))
    lines.extend(_render_platform_system_lines("ClickHouse", getattr(report, "clickhouse", None)))
    lines.extend(_render_platform_object_storage_lines(getattr(report, "object_storage", None)))
    lines.append(f"Healthy: {'yes' if getattr(report, 'ok', False) else 'no'}")
    return tuple(lines)


def _render_cutover_lines(snapshot: CutoverStatusSnapshot) -> list[str]:
    lines = ["Cutover state:"]
    lines.append(f"- mode: {snapshot.mode}")
    lines.append(f"- read path: {snapshot.read_path}")
    lines.append(f"- dual-write active: {'yes' if snapshot.dual_write_active else 'no'}")
    lines.append(f"- write targets: {', '.join(snapshot.write_targets) or 'n/a'}")
    if snapshot.warnings:
        lines.append("- warnings: " + " | ".join(snapshot.warnings))
    return lines


def _render_platform_system_lines(label: str, status: object | None) -> list[str]:
    if status is None:
        return [f"{label}: fail", "- detail: missing status object"]

    lines = [f"{label}: {'ok' if getattr(status, 'ok', False) else 'fail'}"]
    lines.append(f"- endpoint: {getattr(status, 'endpoint', 'n/a')}")
    lines.append(f"- migrations: {getattr(status, 'migration_dir', 'n/a')}")
    expected = getattr(status, "expected_version", None)
    current = getattr(status, "current_version", None)
    available = getattr(status, "available_version", None)
    lines.append(
        f"- schema: current {current if current is not None else 'n/a'} / expected {expected if expected is not None else 'n/a'} / available {available if available is not None else 'n/a'}"
    )
    applied_this_run = tuple(getattr(status, "applied_this_run", ()) or ())
    if applied_this_run:
        lines.append("- applied this run: " + ", ".join(f"V{int(version):03d}" for version in applied_this_run))
    pending = tuple(getattr(status, "pending_versions", ()) or ())
    if pending:
        lines.append("- pending: " + ", ".join(f"V{int(version):03d}" for version in pending))
    unexpected = tuple(getattr(status, "unexpected_versions", ()) or ())
    if unexpected:
        lines.append("- unexpected applied: " + ", ".join(f"V{int(version):03d}" for version in unexpected))
    mismatched = tuple(getattr(status, "mismatched_checksums", ()) or ())
    if mismatched:
        lines.append("- checksum mismatch: " + ", ".join(f"V{int(version):03d}" for version in mismatched))
    lines.append(f"- detail: {getattr(status, 'detail', 'n/a')}")
    error = getattr(status, "error", None)
    if error:
        lines.append(f"- error: {error}")
    return lines


def _render_platform_object_storage_lines(status: object | None) -> list[str]:
    if status is None:
        return ["Object storage: fail", "- detail: missing status object"]

    lines = [f"Object storage: {'ok' if getattr(status, 'ok', False) else 'fail'}"]
    lines.append(f"- endpoint: {getattr(status, 'endpoint_url', 'n/a')}")
    lines.append(f"- bucket: {getattr(status, 'bucket', 'n/a')} ({getattr(status, 'region', 'n/a')})")
    lines.append(
        "- bucket state: exists {exists} | created {created}".format(
            exists="yes" if getattr(status, "bucket_exists", False) else "no",
            created="yes" if getattr(status, "bucket_created", False) else "no",
        )
    )
    prefixes = dict(getattr(status, "prefixes", {}) or {})
    if prefixes:
        lines.append(
            "- prefixes: raw_events={raw_events} | manifests={manifests} | parquet={parquet}".format(
                raw_events=prefixes.get("raw_events") or "n/a",
                manifests=prefixes.get("manifests") or "n/a",
                parquet=prefixes.get("parquet") or "n/a",
            )
        )
    marker_keys = tuple(getattr(status, "ensured_marker_keys", ()) or ())
    if marker_keys:
        lines.append("- ensured marker keys: " + ", ".join(marker_keys))
    probed = tuple(getattr(status, "write_checked_prefixes", ()) or ())
    if probed:
        lines.append("- write probes: " + ", ".join(probed))
    lines.append(f"- detail: {getattr(status, 'detail', 'n/a')}")
    error = getattr(status, "error", None)
    if error:
        lines.append(f"- error: {error}")
    return lines


def _cutover_flag(config: object | None, name: str) -> bool:
    if config is None:
        return False
    if isinstance(config, Mapping):
        cutover = config.get("cutover")
        if isinstance(cutover, Mapping):
            return bool(cutover.get(name, False))
        return False
    cutover = getattr(config, "cutover", None)
    if isinstance(cutover, Mapping):
        return bool(cutover.get(name, False))
    return bool(getattr(cutover, name, False))


__all__ = [
    "CutoverStatusSnapshot",
    "PlatformHealthSnapshot",
    "render_platform_report_lines",
    "render_platform_report_text",
    "summarize_cutover_state",
    "summarize_platform_health",
]
