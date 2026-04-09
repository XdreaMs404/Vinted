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

    class FakeCompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = '{"ok": true, "cycles": [], "resource_snapshots": [], "storage_snapshots": []}'
            self.stderr = ""

    def fake_copy_local_file_to_remote(**kwargs) -> None:
        copied_script["remote_path"] = kwargs["remote_path"]
        copied_script["content"] = kwargs["local_path"].read_text(encoding="utf-8")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeCompletedProcess()

    monkeypatch.setattr(module, "_copy_local_file_to_remote", fake_copy_local_file_to_remote)
    monkeypatch.setattr(module, "_cleanup_remote_snapshot", lambda **kwargs: cleanup_calls.append(str(kwargs["remote_path"])))
    monkeypatch.setattr(module.subprocess, "run", fake_run)

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
    assert kwargs["capture_output"] is True
    assert "input" not in kwargs



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
