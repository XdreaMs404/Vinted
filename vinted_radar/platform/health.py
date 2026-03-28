from __future__ import annotations

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


def render_platform_report_text(report: object) -> str:
    return "\n".join(render_platform_report_lines(report))


def render_platform_report_lines(report: object) -> tuple[str, ...]:
    config = dict(getattr(report, "config") or {})
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
    lines.extend(_render_platform_system_lines("PostgreSQL", getattr(report, "postgres", None)))
    lines.extend(_render_platform_system_lines("ClickHouse", getattr(report, "clickhouse", None)))
    lines.extend(_render_platform_object_storage_lines(getattr(report, "object_storage", None)))
    lines.append(f"Healthy: {'yes' if getattr(report, 'ok', False) else 'no'}")
    return tuple(lines)


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


__all__ = [
    "PlatformHealthSnapshot",
    "render_platform_report_lines",
    "render_platform_report_text",
    "summarize_platform_health",
]
