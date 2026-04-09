from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vinted_radar.services.acquisition_benchmark import (
    build_acquisition_benchmark_report,
    collect_acquisition_benchmark_facts,
    redact_acquisition_benchmark_report,
    render_acquisition_benchmark_markdown,
)

BENCHMARK_DIR = PROJECT_ROOT / ".gsd" / "milestones" / "M003" / "benchmarks"
DEFAULT_REMOTE_REPO_ROOT = "/root/Vinted"
DEFAULT_REMOTE_DB = "/root/Vinted/data/vinted-radar.clean.db"
DEFAULT_REMOTE_PYTHON: str | None = None
DEFAULT_REMOTE_PYTHON_CANDIDATES = (
    "/root/Vinted/venv/bin/python",
    "python3",
    "python",
)
DEFAULT_SAMPLE_INTERVAL_SECONDS = 15.0
DEFAULT_WAIT_BETWEEN_CYCLES_SECONDS = 0.0
DEFAULT_SERVICES = ("vinted-scraper.service", "vinted-dashboard.service")
DEFAULT_VPS_ENV_FILE = PROJECT_ROOT / ".env.vps"
DEFAULT_ASKPASS_SCRIPT = PROJECT_ROOT / ".gsd" / "runtime" / "ssh-askpass.sh"
DEFAULT_SSH_IDENTITY_FILE = str(Path.home() / ".ssh" / "id_ed25519")
DEFAULT_SSH_OPTIONS = (
    "BatchMode=no",
    "PreferredAuthentications=publickey,password",
    "StrictHostKeyChecking=accept-new",
)

PROFILE_REGISTRY: dict[str, dict[str, Any]] = {
    "baseline-fr-page1": {
        "label": "Baseline FR page-limit=1",
        "page_limit": 1,
        "max_leaf_categories": 6,
        "root_scope": "both",
        "min_price": 30.0,
        "max_price": 0.0,
        "state_refresh_limit": 6,
        "request_delay": 3.0,
        "timeout_seconds": 20.0,
    }
}

EXECUTION_MODES: dict[str, dict[str, Any]] = {
    "preserve-live": {
        "destructive": False,
        "preserves_live_service_posture": True,
        "description": (
            "Create a temporary SQLite snapshot on the VPS, run the bounded experiment against the snapshot, "
            "and leave the live DB plus systemd services untouched."
        ),
    },
    "live-db": {
        "destructive": True,
        "preserves_live_service_posture": True,
        "description": (
            "Run the bounded experiment directly against the live SQLite path on the VPS. "
            "This preserves service uptime but mutates the live database."
        ),
    },
}

REMOTE_EXPERIMENT_SCRIPT = r"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import sys
import time


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_remote_snapshot_path(remote_db: str, *, marker: str) -> str:
    source = PurePosixPath(remote_db)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = source.suffix or ".db"
    return str(source.with_name(f"{source.stem}.{marker}-{timestamp}{suffix}"))


def backup_db(source: str, destination: str) -> None:
    source_path = Path(source)
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        destination_path.unlink()
    source_connection = sqlite3.connect(str(source_path), timeout=30.0)
    destination_connection = sqlite3.connect(str(destination_path))
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def query_scalar(db_path: str, sql: str) -> int | None:
    try:
        connection = sqlite3.connect(db_path, timeout=30.0)
        try:
            row = connection.execute(sql).fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        return None
    if not row:
        return None
    value = row[0]
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def file_size(path: str) -> int | None:
    target = Path(path)
    if not target.exists():
        return None
    try:
        return target.stat().st_size
    except OSError:
        return None


def run_command(command: list[str], *, cwd: str | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed with exit code {result.returncode}: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def tail_text(value: str, *, line_limit: int = 80) -> str:
    lines = value.splitlines()
    if len(lines) <= line_limit:
        return value
    return "\n".join(lines[-line_limit:])


def parse_ps_snapshot(ps_output: str) -> tuple[float | None, float | None]:
    lines = [line.strip() for line in ps_output.splitlines() if line.strip()]
    if not lines:
        return (None, None)
    columns = lines[0].split(None, 5)
    if len(columns) < 6:
        return (None, None)
    try:
        cpu_percent = float(columns[2])
    except ValueError:
        cpu_percent = None
    try:
        rss_mb = float(columns[4]) / 1024.0
    except ValueError:
        rss_mb = None
    return (cpu_percent, rss_mb)


def parse_df_snapshot(df_output: str) -> tuple[int | None, int | None]:
    lines = [line.strip() for line in df_output.splitlines() if line.strip()]
    if len(lines) < 2:
        return (None, None)
    columns = lines[-1].split()
    if len(columns) < 4:
        return (None, None)
    try:
        used_bytes = int(columns[2])
        free_bytes = int(columns[3])
    except ValueError:
        return (None, None)
    return (used_bytes, free_bytes)


def capture_resource_snapshot(*, label: str, db_path: str, pid: int | None) -> dict[str, object]:
    ps_command = ["ps", "-o", "pid=,ppid=,%cpu=,%mem=,rss=,etime=,command="]
    if pid is not None:
        ps_command.extend(["-p", str(pid)])
    ps_result = run_command(ps_command)
    vmstat_result = run_command(["vmstat", "1", "2"])
    df_result = run_command(["df", "-B1", str(Path(db_path).parent)])
    cpu_percent, rss_mb = parse_ps_snapshot(ps_result.stdout)
    disk_used_bytes, disk_free_bytes = parse_df_snapshot(df_result.stdout)
    return {
        "captured_at": iso_now(),
        "label": label,
        "cpu_percent": cpu_percent,
        "rss_mb": rss_mb,
        "disk_used_bytes": disk_used_bytes,
        "disk_free_bytes": disk_free_bytes,
        "ps": tail_text(ps_result.stdout),
        "vmstat": tail_text(vmstat_result.stdout),
        "df": tail_text(df_result.stdout),
    }


def capture_storage_snapshot(*, label: str, db_path: str) -> dict[str, object]:
    df_result = run_command(["df", "-B1", str(Path(db_path).parent)])
    disk_used_bytes, disk_free_bytes = parse_df_snapshot(df_result.stdout)
    return {
        "captured_at": iso_now(),
        "label": label,
        "listing_count": query_scalar(db_path, "SELECT COUNT(*) FROM listings"),
        "db_size_bytes": file_size(db_path),
        "artifact_size_bytes": 0,
        "disk_used_bytes": disk_used_bytes,
        "disk_free_bytes": disk_free_bytes,
        "df": tail_text(df_result.stdout),
    }


def capture_service_status(service_names: list[str]) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for service_name in service_names:
        result = run_command(
            [
                "systemctl",
                "show",
                service_name,
                "--no-pager",
                "--property=Id,LoadState,ActiveState,SubState,UnitFileState,MainPID,ExecMainStartTimestamp,FragmentPath",
            ]
        )
        properties: dict[str, object] = {
            "service": service_name,
            "exit_code": result.returncode,
            "raw": tail_text(result.stdout or result.stderr),
        }
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                properties[key] = value
        snapshots.append(properties)
    return snapshots


def build_batch_command(remote_python: str, working_db: str, profile: dict[str, object]) -> list[str]:
    command = [
        remote_python,
        "-m",
        "vinted_radar.cli",
        "batch",
        "--db",
        working_db,
        "--page-limit",
        str(profile["page_limit"]),
        "--root-scope",
        str(profile["root_scope"]),
        "--min-price",
        str(profile["min_price"]),
        "--max-price",
        str(profile["max_price"]),
        "--state-refresh-limit",
        str(profile["state_refresh_limit"]),
        "--request-delay",
        str(profile["request_delay"]),
        "--timeout-seconds",
        str(profile["timeout_seconds"]),
    ]
    if profile.get("max_leaf_categories") is not None:
        command.extend(["--max-leaf-categories", str(profile["max_leaf_categories"])])
    return command


def main() -> int:
    payload_text = os.environ.get("VINTED_BENCHMARK_PAYLOAD")
    if payload_text is None:
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(payload_text)
    remote_repo_root = str(payload["remote_repo_root"])
    remote_db = str(payload["remote_db"])
    remote_python = str(payload["remote_python"])
    mode = str(payload["mode"])
    duration_minutes = float(payload["duration_minutes"])
    sample_interval_seconds = float(payload["sample_interval_seconds"])
    wait_between_cycles_seconds = float(payload.get("wait_between_cycles_seconds") or 0.0)
    profile = dict(payload["profile"])
    service_names = [str(item) for item in list(payload.get("service_names") or [])]

    working_db = remote_db
    temporary_work_db = None
    if mode == "preserve-live":
        temporary_work_db = build_remote_snapshot_path(remote_db, marker="benchmark-work")
        backup_db(remote_db, temporary_work_db)
        working_db = temporary_work_db

    service_status_before = capture_service_status(service_names)
    storage_snapshots = [capture_storage_snapshot(label="before", db_path=working_db)]
    resource_snapshots: list[dict[str, object]] = []
    cycles: list[dict[str, object]] = []

    experiment_started_at = iso_now()
    deadline = time.monotonic() + max(duration_minutes, 0.01) * 60.0
    cycle_index = 0
    failed = False

    while time.monotonic() < deadline:
        cycle_index += 1
        batch_command = build_batch_command(remote_python, working_db, profile)
        cycle_started_at = iso_now()
        process = subprocess.Popen(
            batch_command,
            cwd=remote_repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        cycle_samples = [
            capture_resource_snapshot(label=f"cycle-{cycle_index}-start", db_path=working_db, pid=process.pid)
        ]
        while True:
            try:
                returncode = process.wait(timeout=sample_interval_seconds)
                break
            except subprocess.TimeoutExpired:
                cycle_samples.append(
                    capture_resource_snapshot(
                        label=f"cycle-{cycle_index}-sample-{len(cycle_samples)}",
                        db_path=working_db,
                        pid=process.pid,
                    )
                )
        stdout, stderr = process.communicate()
        cycle_finished_at = iso_now()
        cycle_samples.append(
            capture_resource_snapshot(label=f"cycle-{cycle_index}-finish", db_path=working_db, pid=None)
        )
        resource_snapshots.extend(cycle_samples)
        storage_snapshots.append(capture_storage_snapshot(label=f"cycle-{cycle_index}-after", db_path=working_db))
        cycles.append(
            {
                "cycle_index": cycle_index,
                "started_at": cycle_started_at,
                "finished_at": cycle_finished_at,
                "returncode": returncode,
                "command": batch_command,
                "stdout": tail_text(stdout),
                "stderr": tail_text(stderr),
            }
        )
        if returncode != 0:
            failed = True
            break
        if time.monotonic() >= deadline:
            break
        if wait_between_cycles_seconds > 0:
            time.sleep(wait_between_cycles_seconds)

    experiment_finished_at = iso_now()
    service_status_after = capture_service_status(service_names)
    exported_snapshot = build_remote_snapshot_path(working_db, marker="benchmark-export")
    backup_db(working_db, exported_snapshot)
    if temporary_work_db is not None and Path(temporary_work_db).exists():
        Path(temporary_work_db).unlink()

    result = {
        "ok": not failed,
        "mode": mode,
        "remote_repo_root": remote_repo_root,
        "remote_db": remote_db,
        "working_db": working_db,
        "remote_snapshot_path": exported_snapshot,
        "experiment_started_at": experiment_started_at,
        "experiment_finished_at": experiment_finished_at,
        "service_status_before": service_status_before,
        "service_status_after": service_status_after,
        "storage_snapshots": storage_snapshots,
        "resource_snapshots": resource_snapshots,
        "cycles": cycles,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""".strip()


class BenchmarkRunnerError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded acquisition benchmark directly on the VPS, collect DB/resource snapshots, "
            "and write a local JSON/Markdown artifact bundle under .gsd/milestones/M003/benchmarks/."
        )
    )
    parser.add_argument("--host", required=True, help="VPS hostname or user@hostname, for example 46.225.113.129 or root@46.225.113.129")
    parser.add_argument("--user", help="SSH user when --host does not already include user@. Defaults to VPS_USER from --vps-env-file or root.")
    parser.add_argument("--ssh-port", type=int, help="SSH port. Defaults to VPS_SSH_PORT from --vps-env-file or 22.")
    parser.add_argument("--ssh-binary", default="ssh", help="SSH binary to use. Default: ssh.")
    parser.add_argument("--scp-binary", default="scp", help="SCP binary to use. Default: scp.")
    parser.add_argument(
        "--vps-env-file",
        default=str(DEFAULT_VPS_ENV_FILE),
        help=(
            "Optional env file that can supply VPS_USER, VPS_SSH_PORT, VPS_SSH_KEY_PATH, and SSH_KEY_PASSPHRASE "
            f"for unattended SSH/SCP authentication. Default: {DEFAULT_VPS_ENV_FILE}."
        ),
    )
    parser.add_argument(
        "--ssh-identity-file",
        help=(
            "SSH identity file. Defaults to VPS_SSH_KEY_PATH from --vps-env-file or "
            f"{DEFAULT_SSH_IDENTITY_FILE}."
        ),
    )
    parser.add_argument(
        "--remote-python",
        default=DEFAULT_REMOTE_PYTHON,
        help=(
            "Python binary to use on the VPS. Defaults to auto-detecting the first interpreter that can import "
            "`typer` and `vinted_radar.cli` from the remote repo (prefers /root/Vinted/venv/bin/python, then python3, then python)."
        ),
    )
    parser.add_argument("--remote-repo-root", default=DEFAULT_REMOTE_REPO_ROOT, help=f"Remote repo root. Default: {DEFAULT_REMOTE_REPO_ROOT}.")
    parser.add_argument("--remote-db", default=DEFAULT_REMOTE_DB, help=f"Remote SQLite DB path. Default: {DEFAULT_REMOTE_DB}.")
    parser.add_argument("--profile", required=True, help="Benchmark profile name. Built-in: baseline-fr-page1. Unknown names are allowed when explicit overrides are supplied.")
    parser.add_argument("--duration-minutes", required=True, type=float, help="How long the bounded experiment window may run on the VPS.")
    parser.add_argument("--mode", choices=tuple(EXECUTION_MODES), default="preserve-live", help="preserve-live is non-destructive; live-db mutates the live SQLite database.")
    parser.add_argument("--page-limit", type=int, help="Override the acquisition page_limit for the selected profile.")
    parser.add_argument("--max-leaf-categories", type=int, help="Override the acquisition max_leaf_categories for the selected profile.")
    parser.add_argument("--root-scope", help="Override the acquisition root scope for the selected profile.")
    parser.add_argument("--min-price", type=float, help="Override the acquisition min_price for the selected profile.")
    parser.add_argument("--max-price", type=float, help="Override the acquisition max_price for the selected profile.")
    parser.add_argument("--state-refresh-limit", type=int, help="Override the state refresh probe limit for the selected profile.")
    parser.add_argument("--request-delay", type=float, help="Override the request delay for the selected profile.")
    parser.add_argument("--timeout-seconds", type=float, help="Override the HTTP timeout for the selected profile.")
    parser.add_argument(
        "--sample-interval-seconds",
        type=float,
        default=DEFAULT_SAMPLE_INTERVAL_SECONDS,
        help=f"How often the remote runner samples ps/vmstat while a cycle is running. Default: {DEFAULT_SAMPLE_INTERVAL_SECONDS}.",
    )
    parser.add_argument(
        "--wait-between-cycles-seconds",
        type=float,
        default=DEFAULT_WAIT_BETWEEN_CYCLES_SECONDS,
        help="Optional pause between bounded batch cycles inside the experiment window.",
    )
    parser.add_argument("--output", help="Where to write the local JSON artifact bundle. Defaults under .gsd/milestones/M003/benchmarks/.")
    parser.add_argument("--markdown", help="Where to write the local Markdown summary. Defaults next to the JSON artifact.")
    parser.add_argument(
        "--keep-remote-snapshot",
        action="store_true",
        help="Keep the exported remote SQLite snapshot instead of deleting it after it is copied locally.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _require_binary(args.ssh_binary)
    _require_binary(args.scp_binary)

    vps_env = _load_vps_env_file(args.vps_env_file)
    resolved_user = str(args.user or vps_env.get("VPS_USER") or "root")
    resolved_ssh_port = _coerce_int(args.ssh_port, fallback=vps_env.get("VPS_SSH_PORT"), default=22)
    ssh_identity_file = _resolve_ssh_identity_file(args.ssh_identity_file or vps_env.get("VPS_SSH_KEY_PATH"))
    ssh_env = _build_ssh_subprocess_env(vps_env=vps_env)

    profile = _resolve_profile(args)
    mode_info = dict(EXECUTION_MODES[args.mode])
    output_path, markdown_path = _resolve_artifact_paths(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    ssh_target = _resolve_ssh_target(host=args.host, user=resolved_user)
    resolved_remote_python = _resolve_remote_python(
        requested_remote_python=args.remote_python or vps_env.get("VPS_REMOTE_PYTHON") or vps_env.get("REMOTE_PYTHON"),
        ssh_binary=args.ssh_binary,
        ssh_target=ssh_target,
        ssh_port=resolved_ssh_port,
        ssh_identity_file=ssh_identity_file,
        ssh_env=ssh_env,
        remote_repo_root=args.remote_repo_root,
    )
    remote_result = _run_remote_experiment(
        ssh_binary=args.ssh_binary,
        scp_binary=args.scp_binary,
        ssh_target=ssh_target,
        ssh_port=resolved_ssh_port,
        ssh_identity_file=ssh_identity_file,
        ssh_env=ssh_env,
        remote_python=resolved_remote_python,
        remote_repo_root=args.remote_repo_root,
        remote_db=args.remote_db,
        duration_minutes=args.duration_minutes,
        sample_interval_seconds=args.sample_interval_seconds,
        wait_between_cycles_seconds=args.wait_between_cycles_seconds,
        mode=args.mode,
        profile=profile,
        service_names=DEFAULT_SERVICES,
    )

    temp_snapshot_dir = Path(tempfile.mkdtemp(prefix="vps-benchmark-", dir=str(output_path.parent)))
    local_snapshot = temp_snapshot_dir / Path(str(output_path.stem) + ".sqlite")
    try:
        _copy_remote_snapshot(
            scp_binary=args.scp_binary,
            ssh_port=resolved_ssh_port,
            ssh_target=ssh_target,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
            remote_path=str(remote_result["remote_snapshot_path"]),
            local_path=local_snapshot,
        )

        experiment = collect_acquisition_benchmark_facts(
            local_snapshot,
            experiment_id=f"{args.profile}-{_timestamp_slug(remote_result['experiment_started_at'])}",
            profile=args.profile,
            label=str(profile.get("label") or args.profile),
            window_started_at=str(remote_result["experiment_started_at"]),
            window_finished_at=str(remote_result["experiment_finished_at"]),
            config={
                "runner": {
                    "mode": args.mode,
                    "destructive": mode_info["destructive"],
                    "preserves_live_service_posture": mode_info["preserves_live_service_posture"],
                    "description": mode_info["description"],
                    "duration_minutes": args.duration_minutes,
                    "sample_interval_seconds": args.sample_interval_seconds,
                    "wait_between_cycles_seconds": args.wait_between_cycles_seconds,
                },
                "remote": {
                    "host": args.host,
                    "ssh_target": ssh_target,
                    "ssh_port": resolved_ssh_port,
                    "repo_root": args.remote_repo_root,
                    "db_path": args.remote_db,
                    "identity_file": ssh_identity_file,
                    "vps_env_file": args.vps_env_file,
                },
                "profile": profile,
            },
            storage_snapshots=list(remote_result.get("storage_snapshots") or []),
            resource_snapshots=list(remote_result.get("resource_snapshots") or []),
        )
        facts_db = dict(experiment.get("facts") or {}).get("db")
        if isinstance(facts_db, dict):
            facts_db["path"] = str(remote_result["remote_snapshot_path"])

        report = redact_acquisition_benchmark_report(
            build_acquisition_benchmark_report(
                [experiment],
                generated_at=str(remote_result["experiment_finished_at"]),
            )
        )
        bundle = _build_bundle(
            args=args,
            profile=profile,
            mode_info=mode_info,
            remote_result=remote_result,
            report=report,
            output_path=output_path,
            markdown_path=markdown_path,
            ssh_target=ssh_target,
            ssh_port=resolved_ssh_port,
            ssh_identity_file=ssh_identity_file,
            resolved_remote_python=resolved_remote_python,
            vps_env_file=args.vps_env_file,
        )
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_render_bundle_markdown(bundle), encoding="utf-8")
    finally:
        if local_snapshot.exists():
            local_snapshot.unlink()
        if temp_snapshot_dir.exists():
            shutil.rmtree(temp_snapshot_dir, ignore_errors=True)
        if not args.keep_remote_snapshot:
            _cleanup_remote_snapshot(
                ssh_binary=args.ssh_binary,
                ssh_target=ssh_target,
                ssh_port=resolved_ssh_port,
                ssh_identity_file=ssh_identity_file,
                ssh_env=ssh_env,
                remote_path=str(remote_result.get("remote_snapshot_path") or ""),
            )

    cycle_failures = [cycle for cycle in list(remote_result.get("cycles") or []) if int(cycle.get("returncode") or 0) != 0]
    print(f"Benchmark bundle: {output_path}")
    print(f"Markdown summary: {markdown_path}")
    print(f"Mode: {args.mode} ({'destructive' if mode_info['destructive'] else 'non-destructive'})")
    print(f"Experiment window: {remote_result['experiment_started_at']} -> {remote_result['experiment_finished_at']}")
    print(f"Cycles: {len(remote_result.get('cycles') or [])}")
    if cycle_failures:
        print(f"Cycle failures: {len(cycle_failures)}", file=sys.stderr)
        return 1
    return 0


def _resolve_profile(args: argparse.Namespace) -> dict[str, Any]:
    profile = dict(PROFILE_REGISTRY.get(args.profile) or {})
    overrides = {
        "page_limit": args.page_limit,
        "max_leaf_categories": args.max_leaf_categories,
        "root_scope": args.root_scope,
        "min_price": args.min_price,
        "max_price": args.max_price,
        "state_refresh_limit": args.state_refresh_limit,
        "request_delay": args.request_delay,
        "timeout_seconds": args.timeout_seconds,
    }
    for key, value in overrides.items():
        if value is not None:
            profile[key] = value

    required_keys = (
        "page_limit",
        "root_scope",
        "min_price",
        "max_price",
        "state_refresh_limit",
        "request_delay",
        "timeout_seconds",
    )
    missing = [key for key in required_keys if key not in profile]
    if missing:
        raise SystemExit(
            f"Unknown or incomplete benchmark profile {args.profile!r}. Supply explicit overrides for: {', '.join(missing)}"
        )
    profile.setdefault("label", args.profile)
    return profile


def _resolve_artifact_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.output:
        json_path = Path(args.output)
    else:
        json_path = BENCHMARK_DIR / f"{args.profile}.json"
    if args.markdown:
        markdown_path = Path(args.markdown)
    else:
        markdown_path = json_path.with_suffix(".md")
    return (json_path, markdown_path)


def _resolve_ssh_target(*, host: str, user: str) -> str:
    if "@" in host:
        return host
    return f"{user}@{host}"


def _load_vps_env_file(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = shlex.split(value)[0] if value else value
        values[key] = value
    return values


def _coerce_int(value: int | None, *, fallback: str | None, default: int) -> int:
    if value is not None:
        return int(value)
    if fallback not in (None, ""):
        return int(fallback)
    return default


def _resolve_ssh_identity_file(candidate: str | None) -> str:
    if candidate:
        return str(Path(candidate).expanduser())
    default_path = Path(DEFAULT_SSH_IDENTITY_FILE).expanduser()
    if default_path.exists():
        return str(default_path)
    return ""


def _build_ssh_subprocess_env(*, vps_env: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(vps_env)
    if env.get("SSH_KEY_PASSPHRASE") and DEFAULT_ASKPASS_SCRIPT.exists():
        env.setdefault("DISPLAY", "gsd")
        env["SSH_ASKPASS"] = str(DEFAULT_ASKPASS_SCRIPT)
        env["SSH_ASKPASS_REQUIRE"] = "force"
    return env


def _build_ssh_command_args(*, ssh_port: int, ssh_identity_file: str) -> list[str]:
    command = ["-p", str(ssh_port)]
    for option in DEFAULT_SSH_OPTIONS:
        command.extend(["-o", option])
    if ssh_identity_file:
        command.extend(["-i", ssh_identity_file])
    return command


def _build_scp_command_args(*, ssh_port: int, ssh_identity_file: str) -> list[str]:
    command = ["-P", str(ssh_port)]
    for option in DEFAULT_SSH_OPTIONS:
        command.extend(["-o", option])
    if ssh_identity_file:
        command.extend(["-i", ssh_identity_file])
    return command


def _resolve_remote_python(
    *,
    requested_remote_python: str | None,
    ssh_binary: str,
    ssh_target: str,
    ssh_port: int,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    remote_repo_root: str,
) -> str:
    if requested_remote_python:
        candidates = (requested_remote_python,)
    else:
        candidates = DEFAULT_REMOTE_PYTHON_CANDIDATES

    resolved = _probe_remote_python_candidates(
        candidates=candidates,
        ssh_binary=ssh_binary,
        ssh_target=ssh_target,
        ssh_port=ssh_port,
        ssh_identity_file=ssh_identity_file,
        ssh_env=ssh_env,
        remote_repo_root=remote_repo_root,
    )
    if resolved is not None:
        return resolved

    checked = ", ".join(candidates)
    if requested_remote_python:
        raise BenchmarkRunnerError(
            f"Requested remote python {requested_remote_python!r} could not import `typer` and `vinted_radar.cli` from {remote_repo_root}."
        )
    raise BenchmarkRunnerError(
        "Unable to find a usable remote Python interpreter on the VPS. "
        f"Checked: {checked}. Each candidate must import `typer` and `vinted_radar.cli` from {remote_repo_root}."
    )



def _probe_remote_python_candidates(
    *,
    candidates: tuple[str, ...],
    ssh_binary: str,
    ssh_target: str,
    ssh_port: int,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    remote_repo_root: str,
) -> str | None:
    candidate_tokens = " ".join(shlex.quote(candidate) for candidate in candidates if candidate)
    if not candidate_tokens:
        return None

    probe_script = "\n".join(
        [
            f"cd {shlex.quote(remote_repo_root)} || exit 1",
            f"for candidate in {candidate_tokens}; do",
            '  [ -n "$candidate" ] || continue',
            '  case "$candidate" in',
            '    /*) [ -x "$candidate" ] || continue ;;',
            '  esac',
            "  if \"$candidate\" -c 'import typer, vinted_radar.cli' >/dev/null 2>&1; then",
            '    printf "%s\\n" "$candidate"',
            "    exit 0",
            "  fi",
            "done",
            "exit 1",
        ]
    )
    result = subprocess.run(
        [
            ssh_binary,
            *_build_ssh_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
            ssh_target,
            "sh",
            "-lc",
            probe_script,
        ],
        text=True,
        capture_output=True,
        check=False,
        env=ssh_env,
    )
    if result.returncode != 0:
        return None
    resolved = result.stdout.strip()
    return resolved or None



def _run_remote_experiment(
    *,
    ssh_binary: str,
    scp_binary: str,
    ssh_target: str,
    ssh_port: int,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    remote_python: str,
    remote_repo_root: str,
    remote_db: str,
    duration_minutes: float,
    sample_interval_seconds: float,
    wait_between_cycles_seconds: float,
    mode: str,
    profile: dict[str, Any],
    service_names: tuple[str, ...],
) -> dict[str, Any]:
    payload = {
        "remote_repo_root": remote_repo_root,
        "remote_db": remote_db,
        "remote_python": remote_python,
        "duration_minutes": duration_minutes,
        "sample_interval_seconds": sample_interval_seconds,
        "wait_between_cycles_seconds": wait_between_cycles_seconds,
        "mode": mode,
        "profile": profile,
        "service_names": list(service_names),
    }
    payload_json = json.dumps(payload)
    remote_script_path = f"/tmp/vps-benchmark-runner-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.py"
    local_script = Path(tempfile.mkdtemp(prefix="vps-benchmark-script-", dir=str(BENCHMARK_DIR))) / "remote_runner.py"
    local_script.write_text(REMOTE_EXPERIMENT_SCRIPT, encoding="utf-8")
    try:
        _copy_local_file_to_remote(
            scp_binary=scp_binary,
            ssh_port=ssh_port,
            ssh_target=ssh_target,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
            local_path=local_script,
            remote_path=remote_script_path,
        )
        remote_command = (
            f"VINTED_BENCHMARK_PAYLOAD={shlex.quote(payload_json)} "
            f"{shlex.quote(remote_python)} {shlex.quote(remote_script_path)}"
        )
        result = subprocess.run(
            [
                ssh_binary,
                *_build_ssh_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
                ssh_target,
                remote_command,
            ],
            text=True,
            capture_output=True,
            check=False,
            env=ssh_env,
        )
    finally:
        if local_script.exists():
            shutil.rmtree(local_script.parent, ignore_errors=True)
        _cleanup_remote_snapshot(
            ssh_binary=ssh_binary,
            ssh_target=ssh_target,
            ssh_port=ssh_port,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
            remote_path=remote_script_path,
        )
    if result.returncode != 0:
        raise BenchmarkRunnerError(
            "Remote benchmark runner failed with exit code {code}.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}".format(
                code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BenchmarkRunnerError(
            f"Remote benchmark runner returned invalid JSON: {exc}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        ) from exc


def _copy_local_file_to_remote(
    *,
    scp_binary: str,
    ssh_port: int,
    ssh_target: str,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    local_path: Path,
    remote_path: str,
) -> None:
    result = subprocess.run(
        [
            scp_binary,
            *_build_scp_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
            str(local_path),
            f"{ssh_target}:{remote_path}",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=ssh_env,
    )
    if result.returncode != 0:
        raise BenchmarkRunnerError(
            f"Remote script transfer failed with exit code {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )



def _copy_remote_snapshot(
    *,
    scp_binary: str,
    ssh_port: int,
    ssh_target: str,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    remote_path: str,
    local_path: Path,
) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            scp_binary,
            *_build_scp_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
            f"{ssh_target}:{remote_path}",
            str(local_path),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=ssh_env,
    )
    if result.returncode != 0:
        raise BenchmarkRunnerError(
            f"Remote snapshot transfer failed with exit code {result.returncode}.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _cleanup_remote_snapshot(
    *,
    ssh_binary: str,
    ssh_target: str,
    ssh_port: int,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    remote_path: str,
) -> None:
    if not remote_path:
        return
    subprocess.run(
        [
            ssh_binary,
            *_build_ssh_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
            ssh_target,
            "rm",
            "-f",
            remote_path,
        ],
        text=True,
        capture_output=True,
        check=False,
        env=ssh_env,
    )


def _build_bundle(
    *,
    args: argparse.Namespace,
    profile: dict[str, Any],
    mode_info: dict[str, Any],
    remote_result: dict[str, Any],
    report: dict[str, Any],
    output_path: Path,
    markdown_path: Path,
    ssh_target: str,
    ssh_port: int,
    ssh_identity_file: str,
    resolved_remote_python: str,
    vps_env_file: str,
) -> dict[str, Any]:
    bundle_id = f"vps-benchmark-{args.profile}-{_timestamp_slug(str(remote_result['experiment_finished_at']))}"
    return {
        "bundle_id": bundle_id,
        "generated_at": str(remote_result["experiment_finished_at"]),
        "artifacts": {
            "json": str(output_path),
            "markdown": str(markdown_path),
        },
        "target": {
            "host": args.host,
            "ssh_target": ssh_target,
            "ssh_port": ssh_port,
            "ssh_identity_file": ssh_identity_file,
            "vps_env_file": vps_env_file,
            "remote_repo_root": args.remote_repo_root,
            "remote_db": args.remote_db,
            "remote_python": resolved_remote_python,
        },
        "mode": {
            "name": args.mode,
            "destructive": mode_info["destructive"],
            "preserves_live_service_posture": mode_info["preserves_live_service_posture"],
            "description": mode_info["description"],
        },
        "profile": {
            "name": args.profile,
            **profile,
        },
        "remote_result": remote_result,
        "benchmark_report": report,
    }


def _render_bundle_markdown(bundle: dict[str, Any]) -> str:
    target = dict(bundle.get("target") or {})
    mode = dict(bundle.get("mode") or {})
    profile = dict(bundle.get("profile") or {})
    remote_result = dict(bundle.get("remote_result") or {})
    report = dict(bundle.get("benchmark_report") or {})
    cycles = list(remote_result.get("cycles") or [])
    resource_snapshots = list(remote_result.get("resource_snapshots") or [])

    lines = [
        f"# VPS benchmark bundle — {bundle.get('bundle_id')}",
        "",
        f"Generated at: `{bundle.get('generated_at')}`",
        "",
        "## Execution posture",
        "",
        f"- Host: `{target.get('ssh_target')}`",
        f"- Remote repo: `{target.get('remote_repo_root')}`",
        f"- Remote DB: `{target.get('remote_db')}`",
        f"- Remote Python: `{target.get('remote_python')}`",
        f"- Mode: `{mode.get('name')}`",
        f"- Destructive: `{'yes' if mode.get('destructive') else 'no'}`",
        f"- Preserve live services: `{'yes' if mode.get('preserves_live_service_posture') else 'no'}`",
        f"- Mode note: {mode.get('description') or 'n/a'}",
        "",
        "## Profile",
        "",
        f"- Name: `{profile.get('name')}`",
        f"- Label: `{profile.get('label')}`",
        f"- page_limit: `{profile.get('page_limit')}`",
        f"- max_leaf_categories: `{profile.get('max_leaf_categories')}`",
        f"- root_scope: `{profile.get('root_scope')}`",
        f"- min_price: `{profile.get('min_price')}`",
        f"- max_price: `{profile.get('max_price')}`",
        f"- state_refresh_limit: `{profile.get('state_refresh_limit')}`",
        f"- request_delay: `{profile.get('request_delay')}`",
        f"- timeout_seconds: `{profile.get('timeout_seconds')}`",
        "",
        "## Remote experiment window",
        "",
        f"- Started: `{remote_result.get('experiment_started_at')}`",
        f"- Finished: `{remote_result.get('experiment_finished_at')}`",
        f"- Exported snapshot: `{remote_result.get('remote_snapshot_path')}`",
        f"- Cycles executed: `{len(cycles)}`",
        "",
    ]

    if cycles:
        lines.extend(
            [
                "## Cycle outcomes",
                "",
                "| # | Started | Finished | Exit |",
                "|---|---|---|---:|",
            ]
        )
        for cycle in cycles:
            lines.append(
                "| {cycle_index} | {started_at} | {finished_at} | {returncode} |".format(
                    cycle_index=cycle.get("cycle_index"),
                    started_at=cycle.get("started_at"),
                    finished_at=cycle.get("finished_at"),
                    returncode=cycle.get("returncode"),
                )
            )
        lines.append("")

    if resource_snapshots:
        lines.extend(
            [
                "## Resource snapshots",
                "",
                "| Label | Captured at | CPU % | RAM MB |",
                "|---|---|---:|---:|",
            ]
        )
        for sample in resource_snapshots:
            lines.append(
                "| {label} | {captured_at} | {cpu_percent} | {rss_mb} |".format(
                    label=sample.get("label") or "n/a",
                    captured_at=sample.get("captured_at") or "n/a",
                    cpu_percent=_format_number(sample.get("cpu_percent"), digits=2),
                    rss_mb=_format_number(sample.get("rss_mb"), digits=2),
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Acquisition benchmark report",
            "",
            render_acquisition_benchmark_markdown(report).rstrip(),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _timestamp_slug(value: str) -> str:
    return value.replace(":", "").replace("+00:00", "Z")


def _format_number(value: object, *, digits: int) -> str:
    if value is None or value == "":
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _require_binary(binary_name: str) -> None:
    if shutil.which(binary_name) is None:
        raise SystemExit(f"Required binary not found in PATH: {binary_name}")


if __name__ == "__main__":
    raise SystemExit(main())
