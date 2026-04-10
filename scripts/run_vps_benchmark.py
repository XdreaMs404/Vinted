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
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        "execution_kind": "batch-cycles",
        "page_limit": 1,
        "max_leaf_categories": 6,
        "root_scope": "both",
        "min_price": 30.0,
        "max_price": 0.0,
        "state_refresh_limit": 6,
        "request_delay": 3.0,
        "timeout_seconds": 20.0,
    },
    "dual-lane-smoke": {
        "label": "Dual-lane frontier + expansion smoke",
        "execution_kind": "multi-lane-runtime",
        "default_mode": "live-db",
        "requires_live_runtime_truth": True,
        "stop_services": ["vinted-scraper.service"],
        "expected_lanes": ["frontier", "expansion"],
        "lanes": [
            {
                "lane_name": "frontier",
                "benchmark_label": "frontier-smoke",
                "interval_seconds": 900.0,
                "page_limit": 1,
                "max_leaf_categories": 1,
                "root_scope": "women",
                "min_price": 30.0,
                "max_price": 0.0,
                "state_refresh_limit": 1,
                "request_delay": 3.0,
                "timeout_seconds": 20.0,
                "concurrency": 1,
            },
            {
                "lane_name": "expansion",
                "benchmark_label": "expansion-smoke",
                "interval_seconds": 900.0,
                "page_limit": 1,
                "max_leaf_categories": 1,
                "root_scope": "men",
                "min_price": 30.0,
                "max_price": 0.0,
                "state_refresh_limit": 1,
                "request_delay": 3.0,
                "timeout_seconds": 20.0,
                "concurrency": 1,
            },
        ],
    },
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
import threading
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


def service_is_active(service_name: str) -> bool:
    result = run_command(["systemctl", "is-active", service_name])
    return result.returncode == 0 and result.stdout.strip() == "active"



def control_service(service_name: str, action: str) -> dict[str, object]:
    result = run_command(["systemctl", action, service_name])
    return {
        "service": service_name,
        "action": action,
        "returncode": result.returncode,
        "stdout": tail_text(result.stdout),
        "stderr": tail_text(result.stderr),
        "captured_at": iso_now(),
    }



def serialize_runtime_report(report) -> dict[str, object]:
    return {
        "cycle_id": report.cycle_id,
        "lane_name": report.lane_name,
        "mode": report.mode,
        "status": report.status,
        "phase": report.phase,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "discovery_run_id": report.discovery_run_id,
        "state_probed_count": report.state_probed_count,
        "tracked_listings": report.tracked_listings,
        "freshness_counts": dict(report.freshness_counts),
        "last_error": report.last_error,
        "config": dict(report.config),
        "benchmark_label": report.benchmark_label,
        "state_refresh_summary": None if report.state_refresh_summary is None else dict(report.state_refresh_summary),
    }



def capture_runtime_status_snapshot(*, label: str, db_path: str) -> dict[str, object]:
    from vinted_radar.repository import RadarRepository

    with RadarRepository(db_path) as repository:
        status = repository.runtime_status(limit=5)
    return {
        "captured_at": iso_now(),
        "label": label,
        "status": status,
    }



def collect_benchmark_experiment(
    *,
    db_path: str,
    profile_name: str,
    profile: dict[str, object],
    mode: str,
    remote_repo_root: str,
    remote_db: str,
    remote_python: str,
    duration_minutes: float,
    sample_interval_seconds: float,
    wait_between_cycles_seconds: float,
    service_names: list[str],
    window_started_at: str,
    window_finished_at: str,
    storage_snapshots: list[dict[str, object]],
    resource_snapshots: list[dict[str, object]],
) -> dict[str, object]:
    from vinted_radar.services.acquisition_benchmark import collect_acquisition_benchmark_facts

    experiment_id = f"{profile_name}-{window_started_at.replace(':', '').replace('-', '').replace('+', '_')}"
    return collect_acquisition_benchmark_facts(
        db_path,
        experiment_id=experiment_id,
        profile=profile_name,
        label=str(profile.get("label") or profile_name),
        window_started_at=window_started_at,
        window_finished_at=window_finished_at,
        config={
            "runner": {
                "mode": mode,
                "duration_minutes": duration_minutes,
                "sample_interval_seconds": sample_interval_seconds,
                "wait_between_cycles_seconds": wait_between_cycles_seconds,
                "service_names": list(service_names),
            },
            "remote": {
                "repo_root": remote_repo_root,
                "db_path": remote_db,
                "remote_python": remote_python,
            },
            "profile": dict(profile),
        },
        storage_snapshots=storage_snapshots,
        resource_snapshots=resource_snapshots,
    )



def build_lane_profiles(profile: dict[str, object], *, duration_minutes: float):
    from vinted_radar.services.runtime import RadarRuntimeLaneProfile, RadarRuntimeOptions

    lane_profiles = []
    duration_seconds = max(duration_minutes, 0.01) * 60.0
    for lane in [dict(item) for item in list(profile.get("lanes") or [])]:
        interval_seconds = float(lane.get("interval_seconds") or 60.0)
        computed_max_cycles = max(1, int((duration_seconds + interval_seconds - 1) // interval_seconds))
        lane_profiles.append(
            RadarRuntimeLaneProfile(
                lane_name=str(lane["lane_name"]),
                interval_seconds=interval_seconds,
                max_cycles=int(lane.get("max_cycles") or computed_max_cycles),
                benchmark_label=None if lane.get("benchmark_label") is None else str(lane.get("benchmark_label")),
                options=RadarRuntimeOptions(
                    page_limit=int(lane.get("page_limit") or 1),
                    max_leaf_categories=None if lane.get("max_leaf_categories") is None else int(lane.get("max_leaf_categories")),
                    root_scope=str(lane.get("root_scope") or "both"),
                    request_delay=float(lane.get("request_delay") or 0.0),
                    timeout_seconds=float(lane.get("timeout_seconds") or 20.0),
                    state_refresh_limit=int(lane.get("state_refresh_limit") or 1),
                    concurrency=int(lane.get("concurrency") or 1),
                    min_price=float(lane.get("min_price") or 0.0),
                    max_price=float(lane.get("max_price") or 0.0),
                ),
            )
        )
    return lane_profiles



def run_multi_lane_runtime(
    *,
    remote_repo_root: str,
    working_db: str,
    duration_minutes: float,
    sample_interval_seconds: float,
    profile: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[dict[str, object]]], bool]:
    from vinted_radar.services.runtime import RadarRuntimeService

    runtime_service = RadarRuntimeService(working_db)
    runtime_status_samples: list[dict[str, object]] = []
    resource_snapshots: list[dict[str, object]] = []
    result_holder: dict[str, object] = {}
    error_holder: dict[str, BaseException] = {}

    lane_profiles = build_lane_profiles(profile, duration_minutes=duration_minutes)

    def run_orchestrator() -> None:
        try:
            result_holder["lane_results"] = runtime_service.run_multi_lane_continuous(
                lane_profiles,
                continue_on_error=True,
                start_immediately=True,
            )
        except BaseException as exc:
            error_holder["error"] = exc

    orchestrator_thread = threading.Thread(target=run_orchestrator, name="vps-benchmark-multi-lane", daemon=True)
    orchestrator_thread.start()
    resource_snapshots.append(capture_resource_snapshot(label="multi-lane-start", db_path=working_db, pid=os.getpid()))
    runtime_status_samples.append(capture_runtime_status_snapshot(label="multi-lane-start", db_path=working_db))
    while orchestrator_thread.is_alive():
        time.sleep(max(sample_interval_seconds, 0.1))
        resource_snapshots.append(
            capture_resource_snapshot(
                label=f"multi-lane-sample-{len(resource_snapshots)}",
                db_path=working_db,
                pid=os.getpid(),
            )
        )
        runtime_status_samples.append(
            capture_runtime_status_snapshot(
                label=f"multi-lane-sample-{len(runtime_status_samples)}",
                db_path=working_db,
            )
        )
    orchestrator_thread.join()
    resource_snapshots.append(capture_resource_snapshot(label="multi-lane-finish", db_path=working_db, pid=None))
    runtime_status_samples.append(capture_runtime_status_snapshot(label="multi-lane-finish", db_path=working_db))

    lane_results = {
        lane_name: [serialize_runtime_report(report) for report in list(reports)]
        for lane_name, reports in dict(result_holder.get("lane_results") or {}).items()
    }
    cycles = [
        cycle
        for reports in lane_results.values()
        for cycle in reports
    ]
    cycles.sort(key=lambda item: (str(item.get("started_at") or ""), str(item.get("cycle_id") or "")))
    failed = bool(error_holder)
    if error_holder:
        cycles.append(
            {
                "cycle_id": "runtime-error",
                "lane_name": None,
                "mode": "continuous",
                "status": "failed",
                "phase": "runner",
                "started_at": iso_now(),
                "finished_at": iso_now(),
                "discovery_run_id": None,
                "state_probed_count": 0,
                "tracked_listings": 0,
                "freshness_counts": {},
                "last_error": f"{type(error_holder['error']).__name__}: {error_holder['error']}",
                "config": {},
                "benchmark_label": None,
                "state_refresh_summary": None,
                "returncode": 1,
            }
        )
    for index, cycle in enumerate(cycles, start=1):
        cycle.setdefault("cycle_index", index)
        cycle.setdefault("returncode", 0 if str(cycle.get("status") or "") != "failed" else 1)
    return (cycles, resource_snapshots, runtime_status_samples, lane_results, failed)



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
    export_remote_snapshot = bool(payload.get("export_remote_snapshot", True))

    execution_kind = str(profile.get("execution_kind") or "batch-cycles")
    if remote_repo_root not in sys.path:
        sys.path.insert(0, remote_repo_root)

    working_db = remote_db
    temporary_work_db = None
    if mode == "preserve-live":
        temporary_work_db = build_remote_snapshot_path(remote_db, marker="benchmark-work")
        backup_db(remote_db, temporary_work_db)
        working_db = temporary_work_db

    service_status_before = capture_service_status(service_names)
    storage_snapshots = [capture_storage_snapshot(label="before", db_path=working_db)]
    resource_snapshots: list[dict[str, object]] = []
    runtime_status_samples: list[dict[str, object]] = []
    cycles: list[dict[str, object]] = []
    lane_results: dict[str, list[dict[str, object]]] = {}
    service_actions: list[dict[str, object]] = []

    experiment_started_at = iso_now()
    deadline = time.monotonic() + max(duration_minutes, 0.01) * 60.0
    cycle_index = 0
    failed = False
    stopped_services: list[str] = []

    try:
        if execution_kind == "multi-lane-runtime":
            if mode != "live-db":
                raise RuntimeError("multi-lane-runtime experiments require live-db mode on the VPS")
            for service_name in [str(item) for item in list(profile.get("stop_services") or [])]:
                if not service_is_active(service_name):
                    continue
                stop_action = control_service(service_name, "stop")
                service_actions.append(stop_action)
                if int(stop_action.get("returncode") or 0) != 0:
                    raise RuntimeError(f"failed to stop {service_name}: {stop_action.get('stderr') or stop_action.get('stdout')}")
                stopped_services.append(service_name)
            cycles, lane_resource_snapshots, runtime_status_samples, lane_results, failed = run_multi_lane_runtime(
                remote_repo_root=remote_repo_root,
                working_db=working_db,
                duration_minutes=duration_minutes,
                sample_interval_seconds=sample_interval_seconds,
                profile=profile,
            )
            resource_snapshots.extend(lane_resource_snapshots)
            storage_snapshots.append(capture_storage_snapshot(label="after", db_path=working_db))
        else:
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
    except BaseException as exc:
        failed = True
        cycles.append(
            {
                "cycle_index": len(cycles) + 1,
                "started_at": experiment_started_at,
                "finished_at": iso_now(),
                "returncode": 1,
                "command": ["remote-runner", execution_kind],
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
            }
        )
    finally:
        for service_name in reversed(stopped_services):
            start_action = control_service(service_name, "start")
            service_actions.append(start_action)

    experiment_finished_at = iso_now()
    service_status_after = capture_service_status(service_names)
    benchmark_db_path = working_db
    exported_snapshot = None
    if export_remote_snapshot:
        exported_snapshot = build_remote_snapshot_path(working_db, marker="benchmark-export")
        backup_db(working_db, exported_snapshot)
        benchmark_db_path = exported_snapshot
    benchmark_experiment = None
    benchmark_experiment_error = None
    try:
        benchmark_experiment = collect_benchmark_experiment(
            db_path=benchmark_db_path,
            profile_name=str(profile.get("name") or profile.get("profile_name") or payload.get("profile_name") or "benchmark"),
            profile=profile,
            mode=mode,
            remote_repo_root=remote_repo_root,
            remote_db=remote_db,
            remote_python=remote_python,
            duration_minutes=duration_minutes,
            sample_interval_seconds=sample_interval_seconds,
            wait_between_cycles_seconds=wait_between_cycles_seconds,
            service_names=service_names,
            window_started_at=experiment_started_at,
            window_finished_at=experiment_finished_at,
            storage_snapshots=storage_snapshots,
            resource_snapshots=resource_snapshots,
        )
    except BaseException as exc:
        benchmark_experiment_error = f"{type(exc).__name__}: {exc}"
    if temporary_work_db is not None and Path(temporary_work_db).exists():
        Path(temporary_work_db).unlink()

    result = {
        "ok": not failed,
        "mode": mode,
        "execution_kind": execution_kind,
        "remote_repo_root": remote_repo_root,
        "remote_db": remote_db,
        "working_db": working_db,
        "remote_snapshot_path": exported_snapshot,
        "experiment_started_at": experiment_started_at,
        "experiment_finished_at": experiment_finished_at,
        "service_status_before": service_status_before,
        "service_status_after": service_status_after,
        "service_actions": service_actions,
        "storage_snapshots": storage_snapshots,
        "resource_snapshots": resource_snapshots,
        "runtime_status_samples": runtime_status_samples,
        "lane_results": lane_results,
        "cycles": cycles,
        "benchmark_experiment": benchmark_experiment,
        "benchmark_experiment_error": benchmark_experiment_error,
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
    parser.add_argument("--mode", choices=tuple(EXECUTION_MODES), default=None, help="preserve-live is non-destructive; live-db mutates the live SQLite database.")
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
    parser.add_argument(
        "--verify-base-url",
        help=(
            "Optional public runtime/health base URL to verify while the VPS experiment is active, "
            "for example http://46.225.113.129:8765 or https://radar.example.com/radar."
        ),
    )
    parser.add_argument(
        "--verify-poll-interval-seconds",
        type=float,
        default=10.0,
        help="How often to poll /runtime, /api/runtime, and /health while --verify-base-url is enabled.",
    )
    parser.add_argument(
        "--verify-timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds per serving verification request when --verify-base-url is enabled.",
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
    resolved_mode_name = _resolve_mode_name(args=args, profile=profile)
    mode_info = dict(EXECUTION_MODES[resolved_mode_name])
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
        mode=resolved_mode_name,
        profile=profile,
        service_names=DEFAULT_SERVICES,
        export_remote_snapshot=(args.keep_remote_snapshot or str(profile.get("execution_kind") or "batch-cycles") != "multi-lane-runtime"),
        verify_base_url=args.verify_base_url,
        verify_poll_interval_seconds=args.verify_poll_interval_seconds,
        verify_timeout_seconds=args.verify_timeout_seconds,
    )

    try:
        experiment = _build_experiment_from_remote_result(
            args=args,
            profile=profile,
            mode_info={**mode_info, "name": resolved_mode_name},
            remote_result=remote_result,
            output_path=output_path,
            scp_binary=args.scp_binary,
            resolved_ssh_port=resolved_ssh_port,
            ssh_target=ssh_target,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
        )

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
            resolved_mode_name=resolved_mode_name,
        )
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_render_bundle_markdown(bundle), encoding="utf-8")
    finally:
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
    serving_verification = dict(remote_result.get("serving_verification") or {})
    serving_failed = bool(args.verify_base_url) and not bool(serving_verification.get("ok"))
    print(f"Benchmark bundle: {output_path}")
    print(f"Markdown summary: {markdown_path}")
    print(f"Mode: {resolved_mode_name} ({'destructive' if mode_info['destructive'] else 'non-destructive'})")
    print(f"Experiment window: {remote_result['experiment_started_at']} -> {remote_result['experiment_finished_at']}")
    print(f"Cycles: {len(remote_result.get('cycles') or [])}")
    if args.verify_base_url:
        print(
            "Serving verification: {state}".format(
                state="passed" if not serving_failed else "failed"
            )
        )
    if cycle_failures:
        print(f"Cycle failures: {len(cycle_failures)}", file=sys.stderr)
    if serving_failed:
        print("Serving verification did not capture truthful dual-lane runtime proof.", file=sys.stderr)
    if cycle_failures or serving_failed:
        return 1
    return 0


def _resolve_profile(args: argparse.Namespace) -> dict[str, Any]:
    profile = dict(PROFILE_REGISTRY.get(args.profile) or {})
    execution_kind = str(profile.get("execution_kind") or "batch-cycles")
    if execution_kind == "multi-lane-runtime":
        lanes = profile.get("lanes")
        if not isinstance(lanes, list) or not lanes:
            raise SystemExit(f"Benchmark profile {args.profile!r} must define at least one lane.")
        profile["lanes"] = [dict(item) for item in lanes if isinstance(item, dict)]
        if len(profile["lanes"]) != len(lanes):
            raise SystemExit(f"Benchmark profile {args.profile!r} contains a non-object lane definition.")
        if not profile.get("expected_lanes"):
            profile["expected_lanes"] = [str(item.get("lane_name") or "").strip() for item in profile["lanes"] if str(item.get("lane_name") or "").strip()]
        if not profile.get("expected_lanes"):
            raise SystemExit(f"Benchmark profile {args.profile!r} must name each lane.")
        profile.setdefault("label", args.profile)
        return profile

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
    profile.setdefault("execution_kind", "batch-cycles")
    return profile


def _resolve_mode_name(*, args: argparse.Namespace, profile: dict[str, Any]) -> str:
    requested_mode = args.mode
    resolved_mode = str(requested_mode or profile.get("default_mode") or "preserve-live")
    if bool(profile.get("requires_live_runtime_truth")) and resolved_mode != "live-db":
        raise SystemExit(
            f"Benchmark profile {args.profile!r} requires the live SQLite database so /runtime, /api/runtime, and /health can reflect the active lanes."
        )
    return resolved_mode


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



def _normalize_verify_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        raise BenchmarkRunnerError("--verify-base-url must not be empty when provided.")
    return cleaned



def _fetch_verify_url(url: str, *, timeout_seconds: float) -> tuple[int, str, str]:
    request = Request(url, headers={"User-Agent": "vinted-radar-vps-benchmark/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), response.headers.get("Content-Type", ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), exc.headers.get("Content-Type", ""), body
    except URLError as exc:
        raise BenchmarkRunnerError(f"Serving verification failed for {url}: {exc.reason}") from exc



def _extract_runtime_lane_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lanes: dict[str, dict[str, Any]] = {}
    top_level = payload.get("lane_summaries")
    if isinstance(top_level, dict):
        for lane_name, lane_payload in top_level.items():
            if isinstance(lane_payload, dict):
                lanes[str(lane_name)] = dict(lane_payload)
    runtime_payload = payload.get("runtime")
    if isinstance(runtime_payload, dict) and isinstance(runtime_payload.get("lanes"), dict):
        for lane_name, lane_payload in runtime_payload["lanes"].items():
            if not isinstance(lane_payload, dict):
                continue
            merged = dict(lanes.get(str(lane_name)) or {})
            merged.update({key: value for key, value in lane_payload.items() if key not in merged})
            lanes[str(lane_name)] = merged
    return lanes



def _capture_runtime_serving_sample(
    *,
    base_url: str,
    expected_lanes: tuple[str, ...],
    timeout_seconds: float,
) -> dict[str, Any]:
    runtime_url = base_url + "/runtime"
    runtime_api_url = base_url + "/api/runtime"
    health_url = base_url + "/health"

    runtime_status, runtime_type, runtime_body = _fetch_verify_url(runtime_url, timeout_seconds=timeout_seconds)
    runtime_api_status, runtime_api_type, runtime_api_body = _fetch_verify_url(runtime_api_url, timeout_seconds=timeout_seconds)
    health_status, health_type, health_body = _fetch_verify_url(health_url, timeout_seconds=timeout_seconds)

    runtime_payload = json.loads(runtime_api_body) if "application/json" in runtime_api_type else {}
    health_payload = json.loads(health_body) if "application/json" in health_type else {}
    lane_payload = _extract_runtime_lane_payload(runtime_payload if isinstance(runtime_payload, dict) else {})
    lane_names = sorted(lane_payload)
    lane_statuses = {lane_name: lane_payload.get(lane_name, {}).get("status") for lane_name in lane_names}
    running_lanes = sorted(
        lane_name for lane_name, lane_status in lane_statuses.items() if str(lane_status or "") == "running"
    )
    expected_lane_names = [lane for lane in expected_lanes if lane]
    expected_lanes_present = all(lane in lane_payload for lane in expected_lane_names)
    html_markers_present = all(
        marker in runtime_body
        for marker in ["État par lane", *(f"Lane {lane_name}" for lane_name in expected_lane_names)]
    )
    health_ok = health_status == 200 and "application/json" in health_type and dict(health_payload).get("status") == "ok"
    api_ok = runtime_api_status == 200 and "application/json" in runtime_api_type and bool(runtime_payload)
    runtime_ok = runtime_status == 200 and "text/html" in runtime_type and "Le contrôleur vivant du radar" in runtime_body
    health_runtime_status = None if not isinstance(health_payload, dict) else health_payload.get("current_runtime_status")
    api_runtime_status = None if not isinstance(runtime_payload, dict) else runtime_payload.get("status")

    return {
        "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "runtime": {
            "url": runtime_url,
            "status": runtime_status,
            "content_type": runtime_type,
            "ok": runtime_ok,
            "lane_markers_present": html_markers_present,
        },
        "runtime_api": {
            "url": runtime_api_url,
            "status": runtime_api_status,
            "content_type": runtime_api_type,
            "ok": api_ok,
            "lane_names": lane_names,
            "lane_statuses": lane_statuses,
            "expected_lanes_present": expected_lanes_present,
            "running_lanes": running_lanes,
            "status_value": api_runtime_status,
        },
        "health": {
            "url": health_url,
            "status": health_status,
            "content_type": health_type,
            "ok": health_ok,
            "status_value": None if not isinstance(health_payload, dict) else health_payload.get("status"),
            "current_runtime_status": health_runtime_status,
            "consistent_with_runtime_api": health_runtime_status == api_runtime_status,
        },
        "proof": {
            "lane_truth_visible": runtime_ok and api_ok and html_markers_present and expected_lanes_present,
            "concurrent_running_visible": len(running_lanes) >= len(expected_lane_names) and len(expected_lane_names) > 0,
        },
    }



def _verify_runtime_serving_during_process(
    *,
    process: subprocess.Popen[str],
    base_url: str,
    expected_lanes: tuple[str, ...],
    poll_interval_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    normalized_base_url = _normalize_verify_base_url(base_url)
    samples: list[dict[str, Any]] = []
    startup_failures: list[str] = []
    unexpected_failures: list[str] = []
    proof_observed = False
    final_truth_observed = False

    def record_failure(stage: str, error: Exception) -> None:
        message = "Serving verification {stage} probe failed at {captured_at}: {error_type}: {message}".format(
            stage=stage,
            captured_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            error_type=type(error).__name__,
            message=error,
        )
        if proof_observed:
            unexpected_failures.append(message)
        else:
            startup_failures.append(message)

    def sample_has_truth(sample: dict[str, Any]) -> bool:
        return bool(
            sample["runtime"]["ok"]
            and sample["runtime"]["lane_markers_present"]
            and sample["runtime_api"]["ok"]
            and sample["health"]["ok"]
        )

    def sample_has_tolerable_transition(sample: dict[str, Any]) -> bool:
        runtime_api_status = str(sample["runtime_api"].get("status_value") or "")
        health_status = str(sample["health"].get("current_runtime_status") or "")
        return bool(
            sample_has_truth(sample)
            and sample["runtime_api"].get("expected_lanes_present")
            and not sample["health"].get("consistent_with_runtime_api")
            and runtime_api_status in {"running", "scheduled", "idle"}
            and health_status in {"running", "scheduled", "idle"}
        )

    while process.poll() is None:
        try:
            sample = _capture_runtime_serving_sample(
                base_url=normalized_base_url,
                expected_lanes=expected_lanes,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - defensive runner hardening
            record_failure("in-flight", exc)
            time.sleep(max(poll_interval_seconds, 0.1))
            continue
        samples.append(sample)
        if sample["proof"]["lane_truth_visible"] and sample["proof"]["concurrent_running_visible"]:
            proof_observed = True
        if sample["runtime_api"]["expected_lanes_present"]:
            if not sample_has_truth(sample):
                unexpected_failures.append(
                    "Serving drift observed at {captured_at}: runtime_ok={runtime_ok}, lane_markers={lane_markers}, api_ok={api_ok}, health_ok={health_ok}, health_consistent={health_consistent}".format(
                        captured_at=sample["captured_at"],
                        runtime_ok=sample["runtime"]["ok"],
                        lane_markers=sample["runtime"]["lane_markers_present"],
                        api_ok=sample["runtime_api"]["ok"],
                        health_ok=sample["health"]["ok"],
                        health_consistent=sample["health"]["consistent_with_runtime_api"],
                    )
                )
            elif not sample["health"]["consistent_with_runtime_api"] and not sample_has_tolerable_transition(sample):
                unexpected_failures.append(
                    "Serving drift observed at {captured_at}: runtime_ok={runtime_ok}, lane_markers={lane_markers}, api_ok={api_ok}, health_ok={health_ok}, health_consistent={health_consistent}".format(
                        captured_at=sample["captured_at"],
                        runtime_ok=sample["runtime"]["ok"],
                        lane_markers=sample["runtime"]["lane_markers_present"],
                        api_ok=sample["runtime_api"]["ok"],
                        health_ok=sample["health"]["ok"],
                        health_consistent=sample["health"]["consistent_with_runtime_api"],
                    )
                )
        time.sleep(max(poll_interval_seconds, 0.1))

    try:
        final_sample = _capture_runtime_serving_sample(
            base_url=normalized_base_url,
            expected_lanes=expected_lanes,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - defensive runner hardening
        record_failure("final", exc)
    else:
        samples.append(final_sample)
        if final_sample["runtime_api"]["expected_lanes_present"]:
            final_truth_observed = sample_has_truth(final_sample) and (
                final_sample["health"]["consistent_with_runtime_api"] or sample_has_tolerable_transition(final_sample)
            )

    return {
        "base_url": normalized_base_url,
        "expected_lanes": list(expected_lanes),
        "poll_interval_seconds": poll_interval_seconds,
        "timeout_seconds": timeout_seconds,
        "proof_observed": proof_observed,
        "final_truth_observed": final_truth_observed,
        "startup_failures": startup_failures,
        "unexpected_failures": unexpected_failures,
        "ok": proof_observed and final_truth_observed and not unexpected_failures,
        "samples": samples,
    }



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
    export_remote_snapshot: bool = True,
    verify_base_url: str | None = None,
    verify_poll_interval_seconds: float = 10.0,
    verify_timeout_seconds: float = 20.0,
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
        "profile_name": str(profile.get("profile_name") or profile.get("name") or profile.get("label") or "benchmark"),
        "export_remote_snapshot": export_remote_snapshot,
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
        stdout_dir = Path(tempfile.mkdtemp(prefix="vps-benchmark-stdout-", dir=str(BENCHMARK_DIR)))
        stdout_path = stdout_dir / "remote-stdout.log"
        stderr_path = stdout_dir / "remote-stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(
                [
                    ssh_binary,
                    *_build_ssh_command_args(ssh_port=ssh_port, ssh_identity_file=ssh_identity_file),
                    ssh_target,
                    remote_command,
                ],
                text=True,
                stdout=stdout_file,
                stderr=stderr_file,
                env=ssh_env,
            )
            serving_verification = None
            if verify_base_url:
                expected_lanes = tuple(str(item) for item in list(profile.get("expected_lanes") or []))
                serving_verification = _verify_runtime_serving_during_process(
                    process=process,
                    base_url=verify_base_url,
                    expected_lanes=expected_lanes,
                    poll_interval_seconds=verify_poll_interval_seconds,
                    timeout_seconds=verify_timeout_seconds,
                )
            result_returncode = int(process.wait() or 0)
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    finally:
        if local_script.exists():
            shutil.rmtree(local_script.parent, ignore_errors=True)
        if 'stdout_dir' in locals() and stdout_dir.exists():
            shutil.rmtree(stdout_dir, ignore_errors=True)
        _cleanup_remote_snapshot(
            ssh_binary=ssh_binary,
            ssh_target=ssh_target,
            ssh_port=ssh_port,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
            remote_path=remote_script_path,
        )
    if result_returncode != 0:
        raise BenchmarkRunnerError(
            "Remote benchmark runner failed with exit code {code}.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}".format(
                code=result_returncode,
                stdout=stdout,
                stderr=stderr,
            )
        )
    try:
        remote_result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BenchmarkRunnerError(
            f"Remote benchmark runner returned invalid JSON: {exc}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        ) from exc
    if verify_base_url and serving_verification is not None:
        remote_result["serving_verification"] = serving_verification
    return remote_result


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



def _build_experiment_config(
    *,
    args: argparse.Namespace,
    profile: dict[str, Any],
    mode_info: dict[str, Any],
    ssh_target: str,
    resolved_ssh_port: int,
    ssh_identity_file: str,
) -> dict[str, object]:
    return {
        "runner": {
            "mode": mode_info["name"],
            "destructive": mode_info["destructive"],
            "preserves_live_service_posture": mode_info["preserves_live_service_posture"],
            "description": mode_info["description"],
            "duration_minutes": args.duration_minutes,
            "sample_interval_seconds": args.sample_interval_seconds,
            "wait_between_cycles_seconds": args.wait_between_cycles_seconds,
            "verify_base_url": args.verify_base_url,
            "verify_poll_interval_seconds": args.verify_poll_interval_seconds,
            "verify_timeout_seconds": args.verify_timeout_seconds,
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
    }



def _hydrate_remote_experiment(
    *,
    remote_experiment: dict[str, Any],
    experiment_id: str,
    profile_name: str,
    label: str,
    window_started_at: str,
    window_finished_at: str,
    remote_snapshot_path: str | None,
    remote_db_path: str,
    config: dict[str, object],
    storage_snapshots: list[dict[str, object]],
    resource_snapshots: list[dict[str, object]],
) -> dict[str, object]:
    experiment = dict(remote_experiment)
    experiment["experiment_id"] = experiment_id
    experiment["profile"] = profile_name
    experiment["label"] = label
    experiment["window"] = {
        "started_at": window_started_at,
        "finished_at": window_finished_at,
    }
    experiment["config"] = config
    facts = dict(experiment.get("facts") or {})
    facts["db"] = {"path": remote_snapshot_path or remote_db_path}
    facts["storage_snapshots"] = [dict(item) for item in storage_snapshots]
    facts["resource_snapshots"] = [dict(item) for item in resource_snapshots]
    experiment["facts"] = facts
    return experiment



def _collect_local_snapshot_experiment(
    *,
    args: argparse.Namespace,
    profile: dict[str, Any],
    remote_result: dict[str, Any],
    output_path: Path,
    scp_binary: str,
    resolved_ssh_port: int,
    ssh_target: str,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
    config: dict[str, object],
) -> dict[str, object]:
    remote_snapshot_path = str(remote_result.get("remote_snapshot_path") or "").strip()
    if not remote_snapshot_path:
        benchmark_error = str(remote_result.get("benchmark_experiment_error") or "").strip()
        detail = f" Remote benchmark fact collection error: {benchmark_error}" if benchmark_error else ""
        raise BenchmarkRunnerError(
            "Remote benchmark runner did not provide benchmark facts or an exported snapshot for local collection." + detail
        )
    temp_snapshot_dir = Path(tempfile.mkdtemp(prefix="vps-benchmark-", dir=str(output_path.parent)))
    local_snapshot = temp_snapshot_dir / Path(str(output_path.stem) + ".sqlite")
    try:
        _copy_remote_snapshot(
            scp_binary=scp_binary,
            ssh_port=resolved_ssh_port,
            ssh_target=ssh_target,
            ssh_identity_file=ssh_identity_file,
            ssh_env=ssh_env,
            remote_path=remote_snapshot_path,
            local_path=local_snapshot,
        )

        experiment = collect_acquisition_benchmark_facts(
            local_snapshot,
            experiment_id=f"{args.profile}-{_timestamp_slug(remote_result['experiment_started_at'])}",
            profile=args.profile,
            label=str(profile.get("label") or args.profile),
            window_started_at=str(remote_result["experiment_started_at"]),
            window_finished_at=str(remote_result["experiment_finished_at"]),
            config=config,
            storage_snapshots=list(remote_result.get("storage_snapshots") or []),
            resource_snapshots=list(remote_result.get("resource_snapshots") or []),
        )
        facts_db = dict(experiment.get("facts") or {}).get("db")
        if isinstance(facts_db, dict):
            facts_db["path"] = remote_snapshot_path
        return experiment
    finally:
        if local_snapshot.exists():
            local_snapshot.unlink()
        if temp_snapshot_dir.exists():
            shutil.rmtree(temp_snapshot_dir, ignore_errors=True)



def _build_experiment_from_remote_result(
    *,
    args: argparse.Namespace,
    profile: dict[str, Any],
    mode_info: dict[str, Any],
    remote_result: dict[str, Any],
    output_path: Path,
    scp_binary: str,
    resolved_ssh_port: int,
    ssh_target: str,
    ssh_identity_file: str,
    ssh_env: dict[str, str],
) -> dict[str, object]:
    config = _build_experiment_config(
        args=args,
        profile=profile,
        mode_info=mode_info,
        ssh_target=ssh_target,
        resolved_ssh_port=resolved_ssh_port,
        ssh_identity_file=ssh_identity_file,
    )
    remote_experiment = remote_result.get("benchmark_experiment")
    if isinstance(remote_experiment, dict):
        return _hydrate_remote_experiment(
            remote_experiment=remote_experiment,
            experiment_id=f"{args.profile}-{_timestamp_slug(remote_result['experiment_started_at'])}",
            profile_name=args.profile,
            label=str(profile.get("label") or args.profile),
            window_started_at=str(remote_result["experiment_started_at"]),
            window_finished_at=str(remote_result["experiment_finished_at"]),
            remote_snapshot_path=None if remote_result.get("remote_snapshot_path") in (None, "") else str(remote_result["remote_snapshot_path"]),
            remote_db_path=str(remote_result.get("working_db") or args.remote_db),
            config=config,
            storage_snapshots=[dict(item) for item in list(remote_result.get("storage_snapshots") or [])],
            resource_snapshots=[dict(item) for item in list(remote_result.get("resource_snapshots") or [])],
        )
    return _collect_local_snapshot_experiment(
        args=args,
        profile=profile,
        remote_result=remote_result,
        output_path=output_path,
        scp_binary=scp_binary,
        resolved_ssh_port=resolved_ssh_port,
        ssh_target=ssh_target,
        ssh_identity_file=ssh_identity_file,
        ssh_env=ssh_env,
        config=config,
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
    resolved_mode_name: str,
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
            "name": resolved_mode_name,
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
    lane_results = dict(remote_result.get("lane_results") or {})
    serving_verification = dict(remote_result.get("serving_verification") or {})

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
        f"- execution_kind: `{profile.get('execution_kind') or 'batch-cycles'}`",
        f"- page_limit: `{profile.get('page_limit')}`",
        f"- max_leaf_categories: `{profile.get('max_leaf_categories')}`",
        f"- root_scope: `{profile.get('root_scope')}`",
        f"- min_price: `{profile.get('min_price')}`",
        f"- max_price: `{profile.get('max_price')}`",
        f"- state_refresh_limit: `{profile.get('state_refresh_limit')}`",
        f"- request_delay: `{profile.get('request_delay')}`",
        f"- timeout_seconds: `{profile.get('timeout_seconds')}`",
        "",
    ]

    if isinstance(profile.get("lanes"), list) and profile.get("lanes"):
        lines.extend(
            [
                "## Lane profile",
                "",
                "| Lane | Interval s | Max cycles | Root scope | Page limit | State probes |",
                "|---|---:|---:|---|---:|---:|",
            ]
        )
        for lane in list(profile.get("lanes") or []):
            lane_payload = dict(lane or {})
            lines.append(
                "| {lane_name} | {interval_seconds} | {max_cycles} | {root_scope} | {page_limit} | {state_refresh_limit} |".format(
                    lane_name=lane_payload.get("lane_name") or "n/a",
                    interval_seconds=lane_payload.get("interval_seconds") or "n/a",
                    max_cycles=lane_payload.get("max_cycles") or "auto",
                    root_scope=lane_payload.get("root_scope") or "n/a",
                    page_limit=lane_payload.get("page_limit") or "n/a",
                    state_refresh_limit=lane_payload.get("state_refresh_limit") or "n/a",
                )
            )
        lines.append("")

    lines.extend(
        [
            f"- Started: `{remote_result.get('experiment_started_at')}`",
            f"- Finished: `{remote_result.get('experiment_finished_at')}`",
            f"- Exported snapshot: `{remote_result.get('remote_snapshot_path')}`",
            f"- Cycles executed: `{len(cycles)}`",
            "",
        ]
    )

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

    if lane_results:
        lines.extend(
            [
                "## Lane runtime outcomes",
                "",
                "| Lane | Cycles | Statuses | Benchmarks |",
                "|---|---:|---|---|",
            ]
        )
        for lane_name, reports_for_lane in lane_results.items():
            lane_reports = [dict(item or {}) for item in list(reports_for_lane or [])]
            statuses = ", ".join(str(item.get("status") or "n/a") for item in lane_reports) or "n/a"
            benchmarks = ", ".join(
                str(item.get("benchmark_label") or "n/a") for item in lane_reports if item.get("benchmark_label")
            ) or "n/a"
            lines.append(
                f"| {lane_name} | {len(lane_reports)} | {statuses} | {benchmarks} |"
            )
        lines.append("")

    if serving_verification:
        lines.extend(
            [
                "## Serving verification",
                "",
                f"- Base URL: `{serving_verification.get('base_url')}`",
                f"- Expected lanes: `{', '.join(list(serving_verification.get('expected_lanes') or [])) or 'n/a'}`",
                f"- Proof observed while running: `{'yes' if serving_verification.get('proof_observed') else 'no'}`",
                f"- Final truth observed after completion: `{'yes' if serving_verification.get('final_truth_observed') else 'no'}`",
                f"- Overall status: `{'pass' if serving_verification.get('ok') else 'fail'}`",
                "",
            ]
        )
        startup_failures = list(serving_verification.get("startup_failures") or [])
        if startup_failures:
            lines.append("Startup probe notes:")
            for failure in startup_failures:
                lines.append(f"- {failure}")
            lines.append("")
        failures = list(serving_verification.get("unexpected_failures") or [])
        if failures:
            lines.append("Unexpected failures:")
            for failure in failures:
                lines.append(f"- {failure}")
            lines.append("")
        samples = [dict(item or {}) for item in list(serving_verification.get("samples") or [])]
        if samples:
            lines.extend(
                [
                    "| Captured at | Runtime | Runtime API | Health | Running lanes |",
                    "|---|---:|---:|---:|---|",
                ]
            )
            for sample in samples[:20]:
                lines.append(
                    "| {captured_at} | {runtime_status} | {runtime_api_status} | {health_status} | {running_lanes} |".format(
                        captured_at=sample.get("captured_at") or "n/a",
                        runtime_status=((sample.get("runtime") or {}).get("status") if isinstance(sample.get("runtime"), dict) else "n/a"),
                        runtime_api_status=((sample.get("runtime_api") or {}).get("status") if isinstance(sample.get("runtime_api"), dict) else "n/a"),
                        health_status=((sample.get("health") or {}).get("status") if isinstance(sample.get("health"), dict) else "n/a"),
                        running_lanes=", ".join(list(((sample.get("runtime_api") or {}).get("running_lanes") or []))) or "none",
                    )
                )
            if len(samples) > 20:
                lines.append(f"| … | … | … | … | {len(samples) - 20} additional samples omitted |")
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
