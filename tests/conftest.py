from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC)
