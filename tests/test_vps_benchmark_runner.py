from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType

from tests.test_acquisition_benchmark import _seed_repository_benchmark_db


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_vps_benchmark.py"


def _load_runner_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_vps_benchmark", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _remote_result(*, returncode: int = 0) -> dict[str, object]:
    return {
        "ok": returncode == 0,
        "mode": "preserve-live" if returncode == 0 else "live-db",
        "remote_repo_root": "/root/Vinted",
        "remote_db": "/root/Vinted/data/vinted-radar.clean.db",
        "working_db": "/root/Vinted/data/vinted-radar.clean.db",
        "remote_snapshot_path": "/root/Vinted/data/vinted-radar.clean.benchmark-export-20260409T120000Z.db",
        "experiment_started_at": "2026-04-09T12:00:00+00:00",
        "experiment_finished_at": "2026-04-09T12:30:00+00:00",
        "service_status_before": [
            {"service": "vinted-scraper.service", "ActiveState": "active", "SubState": "running"},
            {"service": "vinted-dashboard.service", "ActiveState": "active", "SubState": "running"},
        ],
        "service_status_after": [
            {"service": "vinted-scraper.service", "ActiveState": "active", "SubState": "running"},
            {"service": "vinted-dashboard.service", "ActiveState": "active", "SubState": "running"},
        ],
        "storage_snapshots": [
            {
                "captured_at": "2026-04-09T12:00:00+00:00",
                "label": "before",
                "listing_count": 100,
                "db_size_bytes": 50_000,
                "artifact_size_bytes": 0,
                "disk_used_bytes": 1_000_000,
                "disk_free_bytes": 5_000_000,
            },
            {
                "captured_at": "2026-04-09T12:30:00+00:00",
                "label": "cycle-1-after",
                "listing_count": 108,
                "db_size_bytes": 51_600,
                "artifact_size_bytes": 0,
                "disk_used_bytes": 1_002_000,
                "disk_free_bytes": 4_998_000,
            },
        ],
        "resource_snapshots": [
            {
                "captured_at": "2026-04-09T12:05:00+00:00",
                "label": "cycle-1-start",
                "cpu_percent": 35.0,
                "rss_mb": 256.0,
                "ps": "123 1 35.0 1.2 262144 00:00:10 python3 -m vinted_radar.cli batch",
                "vmstat": "procs -----------memory----------",
                "df": "Filesystem 1B-blocks Used Available Use% Mounted on",
            },
            {
                "captured_at": "2026-04-09T12:25:00+00:00",
                "label": "cycle-1-finish",
                "cpu_percent": 45.0,
                "rss_mb": 288.0,
                "ps": "",
                "vmstat": "procs -----------memory----------",
                "df": "Filesystem 1B-blocks Used Available Use% Mounted on",
            },
        ],
        "cycles": [
            {
                "cycle_index": 1,
                "started_at": "2026-04-09T12:00:00+00:00",
                "finished_at": "2026-04-09T12:30:00+00:00",
                "returncode": returncode,
                "command": [
                    "python3",
                    "-m",
                    "vinted_radar.cli",
                    "batch",
                    "--db",
                    "/root/Vinted/data/vinted-radar.clean.db",
                    "--page-limit",
                    "1",
                ],
                "stdout": "Cycle: synthetic",
                "stderr": "" if returncode == 0 else "Batch cycle failed",
            }
        ],
    }


def test_run_remote_experiment_uploads_remote_script_and_executes_it(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    captured: dict[str, object] = {}
    copied_script: dict[str, object] = {}
    cleanup_calls: list[str] = []

    class FakeProcess:
        def __init__(self, *, stdout_handle, stderr_handle) -> None:
            self.returncode = 0
            stdout_handle.write('{"ok": true, "cycles": [], "resource_snapshots": [], "storage_snapshots": []}')
            stdout_handle.flush()
            stderr_handle.flush()

        def wait(self):
            return self.returncode

    def fake_copy_local_file_to_remote(**kwargs) -> None:
        copied_script["remote_path"] = kwargs["remote_path"]
        copied_script["content"] = kwargs["local_path"].read_text(encoding="utf-8")

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess(stdout_handle=kwargs["stdout"], stderr_handle=kwargs["stderr"])

    monkeypatch.setattr(module, "_copy_local_file_to_remote", fake_copy_local_file_to_remote)
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: cleanup_calls.append(str(kwargs["remote_path"])))
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    result = module._run_remote_experiment(
        ssh_binary="ssh",
        scp_binary="scp",
        ssh_target="root@46.225.113.129",
        ssh_port=22,
        ssh_identity_file="/tmp/id_ed25519",
        ssh_env={"DISPLAY": "gsd"},
        remote_python="python3",
        remote_repo_root="/root/Vinted",
        remote_db="/root/Vinted/data/vinted-radar.clean.db",
        duration_minutes=15,
        sample_interval_seconds=15,
        wait_between_cycles_seconds=0,
        mode="preserve-live",
        profile={"page_limit": 1},
        service_names=("vinted-scraper.service",),
    )

    assert result["ok"] is True
    assert copied_script["content"] == module.REMOTE_EXPERIMENT_SCRIPT
    assert str(copied_script["remote_path"]).startswith("/tmp/vps-benchmark-runner-")
    assert cleanup_calls == [str(copied_script["remote_path"])]
    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2] == "root@46.225.113.129"
    assert isinstance(command[-1], str)
    assert command[-1].startswith("VINTED_BENCHMARK_PAYLOAD=")
    assert "python3 /tmp/vps-benchmark-runner-" in command[-1]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["env"] == {"DISPLAY": "gsd"}
    assert kwargs["text"] is True
    assert Path(kwargs["stdout"].name).name == "remote-stdout.log"
    assert Path(kwargs["stderr"].name).name == "remote-stderr.log"



def test_resolve_remote_python_auto_detects_virtualenv_before_python3(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner_module()

    captured: dict[str, object] = {}

    class FakeCompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "/root/Vinted/venv/bin/python\n"
            self.stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeCompletedProcess()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    resolved = module._resolve_remote_python(
        requested_remote_python=None,
        ssh_binary="ssh",
        ssh_target="root@46.225.113.129",
        ssh_port=22,
        ssh_identity_file="/tmp/id_ed25519",
        ssh_env={"DISPLAY": "gsd"},
        remote_repo_root="/root/Vinted",
    )

    assert resolved == "/root/Vinted/venv/bin/python"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[-3] == "sh"
    assert command[-2] == "-lc"
    assert "/root/Vinted/venv/bin/python" in command[-1]
    assert "python3" in command[-1]
    assert "import typer, vinted_radar.cli" in command[-1]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["env"] == {"DISPLAY": "gsd"}
    assert kwargs["text"] is True
    assert kwargs["capture_output"] is True



def test_run_vps_benchmark_writes_default_bundle_and_markdown(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    copied_from: dict[str, object] = {}
    cleanup_calls: list[str] = []
    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)

    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")
    monkeypatch.setattr(module, "_run_remote_experiment", lambda **kwargs: _remote_result())

    def fake_copy_remote_snapshot(*, remote_path: str, local_path: Path, **kwargs) -> None:
        copied_from["remote_path"] = remote_path
        shutil.copyfile(db_snapshot, local_path)

    monkeypatch.setattr(module, "_copy_remote_snapshot", fake_copy_remote_snapshot)
    monkeypatch.setattr(
        module,
        "_cleanup_remote_snapshot",
        lambda **kwargs: cleanup_calls.append(str(kwargs["remote_path"])),
    )

    exit_code = module.main(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "baseline-fr-page1",
            "--duration-minutes",
            "30",
        ]
    )

    assert exit_code == 0
    json_path = module.BENCHMARK_DIR / "baseline-fr-page1.json"
    markdown_path = module.BENCHMARK_DIR / "baseline-fr-page1.md"
    assert json_path.exists()
    assert markdown_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert copied_from["remote_path"].endswith("benchmark-export-20260409T120000Z.db")
    assert cleanup_calls == ["/root/Vinted/data/vinted-radar.clean.benchmark-export-20260409T120000Z.db"]
    assert payload["mode"]["name"] == "preserve-live"
    assert payload["mode"]["destructive"] is False
    assert payload["mode"]["preserves_live_service_posture"] is True
    assert payload["target"]["remote_python"] == "/root/Vinted/venv/bin/python"
    assert payload["profile"]["page_limit"] == 1
    assert payload["benchmark_report"]["leaderboard"][0]["experiment_id"].startswith("baseline-fr-page1-")
    assert payload["benchmark_report"]["summary"]["winner_profile"] == "baseline-fr-page1"
    assert "Remote Python: `/root/Vinted/venv/bin/python`" in markdown
    assert "Destructive: `no`" in markdown
    assert "## Resource snapshots" in markdown
    assert "## Acquisition benchmark report" in markdown



def test_run_vps_benchmark_loads_vps_env_transport_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    captured_remote_kwargs: dict[str, object] = {}
    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)

    env_file = tmp_path / ".env.vps"
    env_file.write_text(
        "\n".join(
            [
                "VPS_USER=ops",
                "VPS_SSH_PORT=2202",
                f"VPS_SSH_KEY_PATH={tmp_path / 'id_ed25519'}",
                "SSH_KEY_PASSPHRASE=test-passphrase",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    askpass_script = tmp_path / "ssh-askpass.sh"
    askpass_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(module, "DEFAULT_ASKPASS_SCRIPT", askpass_script)
    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")

    def fake_run_remote_experiment(**kwargs):
        captured_remote_kwargs.update(kwargs)
        return _remote_result()

    monkeypatch.setattr(module, "_run_remote_experiment", fake_run_remote_experiment)

    def fake_copy_remote_snapshot(**kwargs) -> None:
        shutil.copyfile(db_snapshot, kwargs["local_path"])

    monkeypatch.setattr(module, "_copy_remote_snapshot", fake_copy_remote_snapshot)
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: None)

    exit_code = module.main(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "baseline-fr-page1",
            "--duration-minutes",
            "15",
            "--vps-env-file",
            str(env_file),
        ]
    )

    assert exit_code == 0
    assert captured_remote_kwargs["ssh_target"] == "ops@46.225.113.129"
    assert captured_remote_kwargs["ssh_port"] == 2202
    assert captured_remote_kwargs["ssh_identity_file"] == str(tmp_path / "id_ed25519")
    assert captured_remote_kwargs["remote_python"] == "/root/Vinted/venv/bin/python"
    ssh_env = captured_remote_kwargs["ssh_env"]
    assert isinstance(ssh_env, dict)
    assert ssh_env["SSH_KEY_PASSPHRASE"] == "test-passphrase"
    assert ssh_env["SSH_ASKPASS"] == str(askpass_script)
    assert ssh_env["SSH_ASKPASS_REQUIRE"] == "force"
    assert ssh_env["DISPLAY"] == "gsd"



def test_run_vps_benchmark_labels_live_db_mode_as_destructive_and_can_keep_remote_snapshot(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    cleanup_calls: list[str] = []
    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)

    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")

    def fake_run_remote_experiment(**kwargs):
        payload = _remote_result()
        payload["mode"] = "live-db"
        return payload

    monkeypatch.setattr(module, "_run_remote_experiment", fake_run_remote_experiment)

    def fake_copy_remote_snapshot(**kwargs) -> None:
        shutil.copyfile(db_snapshot, kwargs["local_path"])

    monkeypatch.setattr(module, "_copy_remote_snapshot", fake_copy_remote_snapshot)
    monkeypatch.setattr(
        module,
        "_cleanup_remote_snapshot",
        lambda **kwargs: cleanup_calls.append(str(kwargs["remote_path"])),
    )

    json_path = tmp_path / "custom" / "live-db.json"
    markdown_path = tmp_path / "custom" / "live-db.md"
    exit_code = module.main(
        [
            "--host",
            "root@46.225.113.129",
            "--profile",
            "baseline-fr-page1",
            "--duration-minutes",
            "15",
            "--mode",
            "live-db",
            "--keep-remote-snapshot",
            "--output",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["mode"]["name"] == "live-db"
    assert payload["mode"]["destructive"] is True
    assert cleanup_calls == []
    assert "Destructive: `yes`" in markdown



def test_run_vps_benchmark_uses_remote_benchmark_experiment_without_copying_snapshot(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)
    remote_payload = _remote_result()
    remote_payload["mode"] = "live-db"
    remote_payload["benchmark_experiment"] = module.collect_acquisition_benchmark_facts(
        db_snapshot,
        experiment_id="remote-generated",
        profile="dual-lane-smoke",
        label="Dual-lane frontier + expansion smoke",
        window_started_at=str(remote_payload["experiment_started_at"]),
        window_finished_at=str(remote_payload["experiment_finished_at"]),
        storage_snapshots=list(remote_payload.get("storage_snapshots") or []),
        resource_snapshots=list(remote_payload.get("resource_snapshots") or []),
    )

    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")
    monkeypatch.setattr(module, "_run_remote_experiment", lambda **kwargs: remote_payload)
    monkeypatch.setattr(
        module,
        "_copy_remote_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("snapshot copy should be skipped when remote facts exist")),
    )
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: None)

    exit_code = module.main(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "dual-lane-smoke",
            "--duration-minutes",
            "15",
        ]
    )

    assert exit_code == 0
    json_path = module.BENCHMARK_DIR / "dual-lane-smoke.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mode"]["name"] == "live-db"
    assert payload["benchmark_report"]["leaderboard"][0]["experiment_id"].startswith("dual-lane-smoke-")
    assert payload["benchmark_report"]["summary"]["winner_profile"] == "dual-lane-smoke"



def test_run_vps_benchmark_dual_lane_profile_forwards_serving_verification_and_renders_lane_sections(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    captured_remote_kwargs: dict[str, object] = {}
    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)

    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")

    def fake_run_remote_experiment(**kwargs):
        captured_remote_kwargs.update(kwargs)
        payload = _remote_result()
        payload["mode"] = "live-db"
        payload["lane_results"] = {
            "frontier": [{"status": "completed", "benchmark_label": "frontier-smoke"}],
            "expansion": [{"status": "completed", "benchmark_label": "expansion-smoke"}],
        }
        payload["serving_verification"] = {
            "base_url": "http://46.225.113.129:8765",
            "expected_lanes": ["frontier", "expansion"],
            "proof_observed": True,
            "final_truth_observed": True,
            "unexpected_failures": [],
            "ok": True,
            "samples": [
                {
                    "captured_at": "2026-04-09T12:05:00+00:00",
                    "runtime": {"status": 200, "ok": True, "lane_markers_present": True},
                    "runtime_api": {
                        "status": 200,
                        "ok": True,
                        "running_lanes": ["frontier", "expansion"],
                    },
                    "health": {"status": 200, "ok": True},
                }
            ],
        }
        return payload

    monkeypatch.setattr(module, "_run_remote_experiment", fake_run_remote_experiment)

    def fake_copy_remote_snapshot(**kwargs) -> None:
        shutil.copyfile(db_snapshot, kwargs["local_path"])

    monkeypatch.setattr(module, "_copy_remote_snapshot", fake_copy_remote_snapshot)
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: None)

    exit_code = module.main(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "dual-lane-smoke",
            "--duration-minutes",
            "15",
            "--verify-base-url",
            "http://46.225.113.129:8765",
        ]
    )

    assert exit_code == 0
    assert captured_remote_kwargs["mode"] == "live-db"
    assert captured_remote_kwargs["export_remote_snapshot"] is False
    assert captured_remote_kwargs["verify_base_url"] == "http://46.225.113.129:8765"
    assert captured_remote_kwargs["verify_poll_interval_seconds"] == 10.0
    assert captured_remote_kwargs["verify_timeout_seconds"] == 20.0

    json_path = module.BENCHMARK_DIR / "dual-lane-smoke.json"
    markdown_path = module.BENCHMARK_DIR / "dual-lane-smoke.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["mode"]["name"] == "live-db"
    assert payload["profile"]["execution_kind"] == "multi-lane-runtime"
    assert payload["profile"]["expected_lanes"] == ["frontier", "expansion"]
    assert payload["remote_result"]["serving_verification"]["ok"] is True
    assert "## Lane profile" in markdown
    assert "## Lane runtime outcomes" in markdown
    assert "## Serving verification" in markdown
    assert "frontier" in markdown
    assert "expansion" in markdown



def test_resolve_mode_name_rejects_preserve_live_for_dual_lane_profile() -> None:
    module = _load_runner_module()
    args = module.parse_args(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "dual-lane-smoke",
            "--duration-minutes",
            "15",
            "--mode",
            "preserve-live",
        ]
    )

    profile = module._resolve_profile(args)

    try:
        module._resolve_mode_name(args=args, profile=profile)
    except SystemExit as exc:
        assert "requires the live SQLite database" in str(exc)
    else:
        raise AssertionError("expected dual-lane-smoke to reject preserve-live mode")



def test_verify_runtime_serving_during_process_records_probe_errors_without_aborting(monkeypatch) -> None:
    module = _load_runner_module()

    class FakeProcess:
        def __init__(self) -> None:
            self._poll_results = [None, 0]

        def poll(self):
            if self._poll_results:
                return self._poll_results.pop(0)
            return 0

    calls = {"count": 0}

    def fake_capture_runtime_serving_sample(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("health probe timed out")
        return {
            "captured_at": "2026-04-09T12:10:00+00:00",
            "runtime": {"ok": True, "lane_markers_present": True},
            "runtime_api": {
                "ok": True,
                "expected_lanes_present": True,
                "running_lanes": ["frontier", "expansion"],
            },
            "health": {"ok": True, "consistent_with_runtime_api": True},
            "proof": {"lane_truth_visible": True, "concurrent_running_visible": True},
        }

    monkeypatch.setattr(module, "_capture_runtime_serving_sample", fake_capture_runtime_serving_sample)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module._verify_runtime_serving_during_process(
        process=FakeProcess(),
        base_url="http://46.225.113.129:8765",
        expected_lanes=("frontier", "expansion"),
        poll_interval_seconds=10.0,
        timeout_seconds=20.0,
    )

    assert result["base_url"] == "http://46.225.113.129:8765"
    assert result["proof_observed"] is False
    assert result["final_truth_observed"] is True
    assert result["ok"] is False
    assert len(result["samples"]) == 1
    assert len(result["startup_failures"]) == 1
    assert result["unexpected_failures"] == []
    assert "health probe timed out" in result["startup_failures"][0]



def test_verify_runtime_serving_during_process_tolerates_transition_between_runtime_api_and_health(monkeypatch) -> None:
    module = _load_runner_module()

    class FakeProcess:
        def __init__(self) -> None:
            self._poll_results = [None, 0]

        def poll(self):
            if self._poll_results:
                return self._poll_results.pop(0)
            return 0

    calls = {"count": 0}

    def fake_capture_runtime_serving_sample(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "captured_at": "2026-04-10T08:26:05+00:00",
                "runtime": {"ok": True, "lane_markers_present": True},
                "runtime_api": {
                    "ok": True,
                    "expected_lanes_present": True,
                    "running_lanes": ["frontier", "expansion"],
                    "status_value": "running",
                },
                "health": {
                    "ok": True,
                    "consistent_with_runtime_api": False,
                    "current_runtime_status": "scheduled",
                },
                "proof": {"lane_truth_visible": True, "concurrent_running_visible": True},
            }
        return {
            "captured_at": "2026-04-10T08:26:45+00:00",
            "runtime": {"ok": True, "lane_markers_present": True},
            "runtime_api": {
                "ok": True,
                "expected_lanes_present": True,
                "running_lanes": [],
                "status_value": "scheduled",
            },
            "health": {
                "ok": True,
                "consistent_with_runtime_api": True,
                "current_runtime_status": "scheduled",
            },
            "proof": {"lane_truth_visible": True, "concurrent_running_visible": False},
        }

    monkeypatch.setattr(module, "_capture_runtime_serving_sample", fake_capture_runtime_serving_sample)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module._verify_runtime_serving_during_process(
        process=FakeProcess(),
        base_url="http://46.225.113.129:8765",
        expected_lanes=("frontier", "expansion"),
        poll_interval_seconds=10.0,
        timeout_seconds=20.0,
    )

    assert result["proof_observed"] is True
    assert result["final_truth_observed"] is True
    assert result["ok"] is True
    assert result["startup_failures"] == []
    assert result["unexpected_failures"] == []
    assert len(result["samples"]) == 2



def test_run_vps_benchmark_writes_artifacts_even_when_remote_cycle_fails(monkeypatch, tmp_path: Path) -> None:
    module = _load_runner_module()
    module.BENCHMARK_DIR = tmp_path / "benchmarks"
    module.BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    db_snapshot = tmp_path / "seeded-benchmark.db"
    _seed_repository_benchmark_db(db_snapshot)

    monkeypatch.setattr(module, "_require_binary", lambda binary_name: None)
    monkeypatch.setattr(module, "_resolve_remote_python", lambda **kwargs: "/root/Vinted/venv/bin/python")
    monkeypatch.setattr(module, "_run_remote_experiment", lambda **kwargs: _remote_result(returncode=1))

    def fake_copy_remote_snapshot(**kwargs) -> None:
        shutil.copyfile(db_snapshot, kwargs["local_path"])

    monkeypatch.setattr(module, "_copy_remote_snapshot", fake_copy_remote_snapshot)
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: None)

    exit_code = module.main(
        [
            "--host",
            "46.225.113.129",
            "--profile",
            "baseline-fr-page1",
            "--duration-minutes",
            "15",
        ]
    )

    assert exit_code == 1
    json_path = module.BENCHMARK_DIR / "baseline-fr-page1.json"
    markdown_path = module.BENCHMARK_DIR / "baseline-fr-page1.md"
    assert json_path.exists()
    assert markdown_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload["remote_result"]["cycles"][0]["returncode"] == 1
    assert payload["benchmark_report"]["summary"]["winner_profile"] == "baseline-fr-page1"
