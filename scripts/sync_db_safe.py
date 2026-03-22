from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vinted_radar.db_health import inspect_sqlite_database

REMOTE_BACKUP_SCRIPT = r"""
import pathlib
import sqlite3
import sys

source = pathlib.Path(sys.argv[1])
snapshot = pathlib.Path(sys.argv[2])
snapshot.parent.mkdir(parents=True, exist_ok=True)
if snapshot.exists():
    snapshot.unlink()
source_connection = sqlite3.connect(str(source), timeout=30.0)
snapshot_connection = sqlite3.connect(str(snapshot))
try:
    source_connection.backup(snapshot_connection)
finally:
    snapshot_connection.close()
    source_connection.close()
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a consistent SQLite snapshot on a VPS, copy it locally, health-check it, then atomically promote it.",
    )
    parser.add_argument("--remote-host", required=True, help="SSH host, for example root@46.225.113.129")
    parser.add_argument("--remote-db", required=True, help="Absolute remote SQLite path, for example /root/Vinted/data/vinted-radar.db")
    parser.add_argument("--destination", default="data/vinted-radar.db", help="Local destination path for the promoted database")
    parser.add_argument("--ssh-binary", default="ssh", help="SSH binary to use")
    parser.add_argument("--scp-binary", default="scp", help="SCP binary to use")
    parser.add_argument("--remote-python", default="python3", help="Python binary to use on the remote host")
    parser.add_argument("--keep-remote-snapshot", action="store_true", help="Keep the remote snapshot file instead of deleting it after transfer")
    parser.add_argument("--integrity", action="store_true", help="Run full PRAGMA integrity_check locally before promotion")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _require_binary(args.ssh_binary)
    _require_binary(args.scp_binary)

    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _build_sidecar_path(destination, marker="syncing")
    rejected_path = _build_sidecar_path(destination, marker=f"rejected-{_timestamp()}")
    remote_snapshot = _build_remote_snapshot_path(args.remote_db)

    if temp_path.exists():
        temp_path.unlink()

    try:
        print(f"[1/4] Creating remote snapshot {remote_snapshot} from {args.remote_db}")
        _run(
            [args.ssh_binary, args.remote_host, _remote_backup_command(args.remote_python, args.remote_db, remote_snapshot)],
            label="remote backup",
        )

        print(f"[2/4] Copying snapshot to {temp_path}")
        _run(
            [args.scp_binary, f"{args.remote_host}:{remote_snapshot}", str(temp_path)],
            label="snapshot transfer",
        )

        print("[3/4] Verifying local snapshot health")
        report = inspect_sqlite_database(temp_path, include_integrity_check=args.integrity, probe_tables=True)
        _print_health_report(report)
        if not report["healthy"]:
            temp_path.replace(rejected_path)
            print(f"Refused to promote unhealthy copy. Rejected snapshot kept at {rejected_path}", file=sys.stderr)
            return 1

        print(f"[4/4] Promoting {temp_path} -> {destination}")
        temp_path.replace(destination)
        print(f"Promotion complete: {destination}")
        return 0
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if not args.keep_remote_snapshot:
            _cleanup_remote_snapshot(args.ssh_binary, args.remote_host, remote_snapshot)


def _remote_backup_command(remote_python: str, remote_db: str, remote_snapshot: str) -> str:
    return " ".join(
        [
            shlex.quote(remote_python),
            "-c",
            shlex.quote(REMOTE_BACKUP_SCRIPT),
            shlex.quote(remote_db),
            shlex.quote(remote_snapshot),
        ]
    )


def _cleanup_remote_snapshot(ssh_binary: str, remote_host: str, remote_snapshot: str) -> None:
    cleanup_command = f"rm -f {shlex.quote(remote_snapshot)}"
    subprocess.run([ssh_binary, remote_host, cleanup_command], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _build_remote_snapshot_path(remote_db: str) -> str:
    source = PurePosixPath(remote_db)
    marker = f"snapshot-{_timestamp()}"
    snapshot_name = f"{source.stem}.{marker}{source.suffix or '.db'}"
    return str(source.with_name(snapshot_name))


def _build_sidecar_path(path: Path, *, marker: str) -> Path:
    suffix = path.suffix or ".db"
    stem = path.name[:-len(suffix)] if path.suffix else path.name
    return path.with_name(f"{stem}.{marker}{suffix}")


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _require_binary(binary_name: str) -> None:
    if shutil.which(binary_name) is None:
        raise SystemExit(f"Required binary not found in PATH: {binary_name}")


def _run(command: list[str], *, label: str) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"{label} failed with exit code {exc.returncode}") from exc


def _print_health_report(report: dict[str, object]) -> None:
    print(f"  exists: {report['exists']}")
    print(f"  size_bytes: {report['size_bytes']}")
    for name, check in dict(report.get("checks") or {}).items():
        if check.get("ok"):
            print(f"  {name}: ok")
        elif check.get("error"):
            print(f"  {name}: {check['error']}")
        else:
            messages = "; ".join(str(item) for item in list(check.get("messages") or [])[:3]) or "check failed"
            print(f"  {name}: {messages}")
    for table in list(report.get("tables") or []):
        if not table.get("exists"):
            print(f"  table {table['table']}: missing")
            continue
        if table.get("count_ok") and table.get("sample_ok"):
            print(f"  table {table['table']}: count ok ({table['row_count']} rows), sample ok")
            continue
        print(
            "  table {table}: count={count}; sample={sample}".format(
                table=table["table"],
                count=table.get("count_error") or f"ok ({table['row_count']} rows)",
                sample=table.get("sample_error") or "ok",
            )
        )
    print(f"  healthy: {report['healthy']}")


if __name__ == "__main__":
    raise SystemExit(main())
