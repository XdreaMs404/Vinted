from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Iterator
from urllib.parse import urlsplit
import uuid

import pytest

from vinted_radar.platform.config import (
    CLICKHOUSE_PASSWORD_ENV,
    CLICKHOUSE_URL_ENV,
    CLICKHOUSE_USERNAME_ENV,
    OBJECT_STORE_ACCESS_KEY_ENV,
    OBJECT_STORE_BUCKET_ENV,
    OBJECT_STORE_ENDPOINT_ENV,
    OBJECT_STORE_PREFIX_ENV,
    OBJECT_STORE_SECRET_KEY_ENV,
    POSTGRES_DSN_ENV,
    PlatformConfig,
    load_platform_config,
)


@dataclass(frozen=True, slots=True)
class DataPlatformSmokeStack:
    repo_root: Path
    compose_file: Path
    compose_project: str
    env: dict[str, str]
    config: PlatformConfig
    ports: dict[str, int]

    def run_compose(
        self,
        *args: str,
        timeout: int = 240,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return _run_command(
            [
                "docker",
                "compose",
                "-p",
                self.compose_project,
                "-f",
                str(self.compose_file),
                *args,
            ],
            cwd=self.repo_root,
            env=self.env,
            timeout=timeout,
            check=check,
        )

    def run_cli(
        self,
        *args: str,
        timeout: int = 180,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return _run_command(
            [sys.executable, "-m", "vinted_radar.cli", *args],
            cwd=self.repo_root,
            env=self.env,
            timeout=timeout,
            check=check,
        )

    def compose_ps(self) -> str:
        result = self.run_compose("ps", check=False, timeout=60)
        parts = [part.strip() for part in (result.stdout, result.stderr) if part.strip()]
        return "\n".join(parts)


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def docker_available() -> bool:
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.returncode == 0


@pytest.fixture
def data_platform_stack(repo_root: Path, docker_available: bool) -> Iterator[DataPlatformSmokeStack]:
    if not docker_available:
        pytest.skip("Docker daemon is not available for the data-platform smoke test.")

    compose_file = repo_root / "infra" / "docker-compose.data-platform.yml"
    suffix = uuid.uuid4().hex[:10].lower()
    ports = {
        "postgres": _pick_free_port(),
        "clickhouse_http": _pick_free_port(),
        "clickhouse_native": _pick_free_port(),
        "object_storage": _pick_free_port(),
        "object_storage_console": _pick_free_port(),
    }
    env = os.environ.copy()
    env.update(
        {
            "VINTED_RADAR_PLATFORM_POSTGRES_PORT": str(ports["postgres"]),
            "VINTED_RADAR_PLATFORM_CLICKHOUSE_HTTP_PORT": str(ports["clickhouse_http"]),
            "VINTED_RADAR_PLATFORM_CLICKHOUSE_NATIVE_PORT": str(ports["clickhouse_native"]),
            "VINTED_RADAR_PLATFORM_OBJECT_STORE_PORT": str(ports["object_storage"]),
            "VINTED_RADAR_PLATFORM_OBJECT_STORE_CONSOLE_PORT": str(ports["object_storage_console"]),
            POSTGRES_DSN_ENV: f"postgresql://vinted:vinted@127.0.0.1:{ports['postgres']}/vinted_radar",
            CLICKHOUSE_URL_ENV: f"http://127.0.0.1:{ports['clickhouse_http']}",
            CLICKHOUSE_USERNAME_ENV: "default",
            CLICKHOUSE_PASSWORD_ENV: "",
            OBJECT_STORE_ENDPOINT_ENV: f"http://127.0.0.1:{ports['object_storage']}",
            OBJECT_STORE_BUCKET_ENV: f"vinted-radar-smoke-{suffix}",
            OBJECT_STORE_PREFIX_ENV: f"vinted-radar/smoke-{suffix}",
            OBJECT_STORE_ACCESS_KEY_ENV: "minioadmin",
            OBJECT_STORE_SECRET_KEY_ENV: "minioadmin",
        }
    )
    stack = DataPlatformSmokeStack(
        repo_root=repo_root,
        compose_file=compose_file,
        compose_project=f"vinted-radar-smoke-{suffix}",
        env=env,
        config=load_platform_config(env=env),
        ports=ports,
    )

    try:
        try:
            stack.run_compose("up", "-d", "--wait")
        except AssertionError as exc:
            logs = stack.run_compose("logs", "--no-color", check=False, timeout=120)
            raise AssertionError(
                f"Failed to start data-platform smoke stack.\n\n{exc}\n\nCompose logs stdout:\n{logs.stdout}\nCompose logs stderr:\n{logs.stderr}"
            ) from exc
        yield stack
    finally:
        stack.run_compose("down", "-v", "--remove-orphans", check=False, timeout=240)


@pytest.fixture
def postgres_connect(data_platform_stack: DataPlatformSmokeStack):
    def _connect():
        import psycopg

        deadline = time.monotonic() + 60
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                connection = psycopg.connect(data_platform_stack.config.postgres.dsn, connect_timeout=2)
                connection.execute("SELECT 1").fetchone()
                return connection
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(1)
        raise AssertionError(f"PostgreSQL never became ready: {type(last_error).__name__}: {last_error}")

    return _connect


@pytest.fixture
def clickhouse_client_factory(data_platform_stack: DataPlatformSmokeStack):
    def _connect(*, database: str | None = None):
        import clickhouse_connect

        parts = urlsplit(data_platform_stack.config.clickhouse.url)
        deadline = time.monotonic() + 60
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            client = None
            try:
                client = clickhouse_connect.get_client(
                    host=parts.hostname or "127.0.0.1",
                    port=parts.port or 8123,
                    username=data_platform_stack.config.clickhouse.username,
                    password=data_platform_stack.config.clickhouse.password,
                    database=database or data_platform_stack.config.clickhouse.database,
                    secure=parts.scheme == "https",
                )
                client.command("SELECT 1")
                return client
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                _close_quietly(client)
                time.sleep(1)
        raise AssertionError(f"ClickHouse never became ready: {type(last_error).__name__}: {last_error}")

    return _connect


@pytest.fixture
def object_storage_client_factory(data_platform_stack: DataPlatformSmokeStack):
    def _connect():
        import boto3
        from botocore.config import Config as BotoConfig

        deadline = time.monotonic() + 60
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            client = None
            try:
                client = boto3.client(
                    "s3",
                    endpoint_url=data_platform_stack.config.object_storage.endpoint_url,
                    aws_access_key_id=data_platform_stack.config.object_storage.access_key_id,
                    aws_secret_access_key=data_platform_stack.config.object_storage.secret_access_key,
                    region_name=data_platform_stack.config.object_storage.region,
                    config=BotoConfig(s3={"addressing_style": "path"}),
                )
                client.list_buckets()
                return client
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                _close_quietly(client)
                time.sleep(1)
        raise AssertionError(f"MinIO never became ready: {type(last_error).__name__}: {last_error}")

    return _connect


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            "Command failed ({code}): {command}\n\nstdout:\n{stdout}\n\nstderr:\n{stderr}".format(
                code=result.returncode,
                command=" ".join(command),
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    return result


def _close_quietly(resource: object | None) -> None:
    if resource is None:
        return
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001
            pass
