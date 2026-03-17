from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vinted_radar.storage.repository import Repository


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "radar.db"


@pytest.fixture
def repository(db_path: Path) -> Iterator[Repository]:
    repo = Repository(db_path)
    try:
        yield repo
    finally:
        repo.close()


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC)
