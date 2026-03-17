from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

from vinted_radar.repository import RadarRepository
from vinted_radar.scoring import load_listing_scores
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryRunReport, build_default_service
from vinted_radar.services.state_refresh import StateRefreshReport, build_default_state_refresh_service


@dataclass(frozen=True, slots=True)
class RadarRuntimeOptions:
    page_limit: int = 1
    max_leaf_categories: int | None = None
    root_scope: str = "both"
    request_delay: float = 0.5
    timeout_seconds: float = 20.0
    state_refresh_limit: int = 10

    def as_config(self) -> dict[str, object]:
        return {
            "page_limit": self.page_limit,
            "max_leaf_categories": self.max_leaf_categories,
            "root_scope": self.root_scope,
            "request_delay": self.request_delay,
            "timeout_seconds": self.timeout_seconds,
            "state_refresh_limit": self.state_refresh_limit,
        }


@dataclass(frozen=True, slots=True)
class RadarRuntimeCycleReport:
    cycle_id: str
    mode: str
    status: str
    phase: str
    started_at: str
    finished_at: str | None
    discovery_run_id: str | None
    state_probed_count: int
    tracked_listings: int
    freshness_counts: dict[str, int]
    last_error: str | None
    config: dict[str, object]
    discovery_report: DiscoveryRunReport | None = None
    state_report: StateRefreshReport | None = None


class RadarRuntimeService:
    def __init__(
        self,
        db_path: str | Path,
        *,
        discovery_service_factory: Callable[..., object] = build_default_service,
        state_refresh_service_factory: Callable[..., object] = build_default_state_refresh_service,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.db_path = Path(db_path)
        self.discovery_service_factory = discovery_service_factory
        self.state_refresh_service_factory = state_refresh_service_factory
        self.sleep_fn = sleep_fn

    def run_cycle(
        self,
        options: RadarRuntimeOptions,
        *,
        mode: str,
        interval_seconds: float | None = None,
        raise_on_error: bool = True,
    ) -> RadarRuntimeCycleReport:
        with RadarRepository(self.db_path) as repository:
            cycle_id = repository.start_runtime_cycle(
                mode=mode,
                phase="starting",
                interval_seconds=interval_seconds,
                state_probe_limit=options.state_refresh_limit,
                config=options.as_config(),
            )
            cycle_row = repository.runtime_cycle(cycle_id)
        if cycle_row is None:
            raise RuntimeError(f"Runtime cycle {cycle_id} was not persisted.")

        current_phase = "starting"
        discovery_report: DiscoveryRunReport | None = None
        state_report: StateRefreshReport | None = None

        try:
            current_phase = "discovery"
            self._update_phase(cycle_id, current_phase)
            discovery_service = self.discovery_service_factory(
                db_path=str(self.db_path),
                timeout_seconds=options.timeout_seconds,
                request_delay=options.request_delay,
            )
            try:
                discovery_report = discovery_service.run(
                    DiscoveryOptions(
                        page_limit=options.page_limit,
                        max_leaf_categories=options.max_leaf_categories,
                        root_scope=options.root_scope,
                        request_delay=options.request_delay,
                    )
                )
            finally:
                discovery_service.repository.close()

            current_phase = "state_refresh"
            self._update_phase(cycle_id, current_phase)
            state_refresh_service = self.state_refresh_service_factory(
                db_path=str(self.db_path),
                timeout_seconds=options.timeout_seconds,
                request_delay=options.request_delay,
            )
            try:
                state_report = state_refresh_service.refresh(limit=options.state_refresh_limit)
            finally:
                state_refresh_service.repository.close()

            current_phase = "summarizing"
            self._update_phase(cycle_id, current_phase)
            tracked_listings, freshness_counts = self._runtime_snapshot()
            self._complete_cycle(
                cycle_id,
                status="completed",
                phase="completed",
                discovery_run_id=discovery_report.run_id,
                state_probed_count=state_report.probed_count,
                tracked_listings=tracked_listings,
                freshness_counts=freshness_counts,
                last_error=None,
            )
            return self._build_report(cycle_id, discovery_report=discovery_report, state_report=state_report)
        except KeyboardInterrupt:
            tracked_listings, freshness_counts = self._runtime_snapshot()
            self._complete_cycle(
                cycle_id,
                status="interrupted",
                phase=current_phase,
                discovery_run_id=None if discovery_report is None else discovery_report.run_id,
                state_probed_count=0 if state_report is None else state_report.probed_count,
                tracked_listings=tracked_listings,
                freshness_counts=freshness_counts,
                last_error="Interrupted by operator.",
            )
            raise
        except Exception as exc:  # noqa: BLE001
            tracked_listings, freshness_counts = self._runtime_snapshot()
            failure_report = self._complete_and_build_failure_report(
                cycle_id,
                phase=current_phase,
                discovery_run_id=None if discovery_report is None else discovery_report.run_id,
                state_probed_count=0 if state_report is None else state_report.probed_count,
                tracked_listings=tracked_listings,
                freshness_counts=freshness_counts,
                last_error=f"{type(exc).__name__}: {exc}",
                discovery_report=discovery_report,
                state_report=state_report,
            )
            if raise_on_error:
                raise
            return failure_report

    def run_continuous(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        max_cycles: int | None = None,
        continue_on_error: bool = True,
        on_cycle_complete: Callable[[RadarRuntimeCycleReport], None] | None = None,
    ) -> list[RadarRuntimeCycleReport]:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be at least 1 when provided")

        reports: list[RadarRuntimeCycleReport] = []
        cycle_count = 0
        while max_cycles is None or cycle_count < max_cycles:
            report = self.run_cycle(
                options,
                mode="continuous",
                interval_seconds=interval_seconds,
                raise_on_error=not continue_on_error,
            )
            reports.append(report)
            cycle_count += 1
            if on_cycle_complete is not None:
                on_cycle_complete(report)
            if max_cycles is not None and cycle_count >= max_cycles:
                break
            self.sleep_fn(interval_seconds)
        return reports

    def _update_phase(self, cycle_id: str, phase: str) -> None:
        with RadarRepository(self.db_path) as repository:
            repository.update_runtime_cycle_phase(cycle_id, phase=phase)

    def _complete_cycle(
        self,
        cycle_id: str,
        *,
        status: str,
        phase: str,
        discovery_run_id: str | None,
        state_probed_count: int,
        tracked_listings: int,
        freshness_counts: dict[str, int],
        last_error: str | None,
    ) -> None:
        with RadarRepository(self.db_path) as repository:
            repository.complete_runtime_cycle(
                cycle_id,
                status=status,
                phase=phase,
                discovery_run_id=discovery_run_id,
                state_probed_count=state_probed_count,
                tracked_listings=tracked_listings,
                freshness_counts=freshness_counts,
                last_error=last_error,
            )

    def _complete_and_build_failure_report(
        self,
        cycle_id: str,
        *,
        phase: str,
        discovery_run_id: str | None,
        state_probed_count: int,
        tracked_listings: int,
        freshness_counts: dict[str, int],
        last_error: str,
        discovery_report: DiscoveryRunReport | None,
        state_report: StateRefreshReport | None,
    ) -> RadarRuntimeCycleReport:
        self._complete_cycle(
            cycle_id,
            status="failed",
            phase=phase,
            discovery_run_id=discovery_run_id,
            state_probed_count=state_probed_count,
            tracked_listings=tracked_listings,
            freshness_counts=freshness_counts,
            last_error=last_error,
        )
        return self._build_report(cycle_id, discovery_report=discovery_report, state_report=state_report)

    def _runtime_snapshot(self) -> tuple[int, dict[str, int]]:
        try:
            with RadarRepository(self.db_path) as repository:
                freshness = repository.freshness_summary()
                tracked_listings = len(load_listing_scores(repository))
        except Exception:  # noqa: BLE001
            return 0, {
                "first-pass-only": 0,
                "fresh-followup": 0,
                "aging-followup": 0,
                "stale-followup": 0,
            }
        overall = freshness["overall"]
        return tracked_listings, {
            "first-pass-only": int(overall.get("first-pass-only", 0) or 0),
            "fresh-followup": int(overall.get("fresh-followup", 0) or 0),
            "aging-followup": int(overall.get("aging-followup", 0) or 0),
            "stale-followup": int(overall.get("stale-followup", 0) or 0),
        }

    def _build_report(
        self,
        cycle_id: str,
        *,
        discovery_report: DiscoveryRunReport | None,
        state_report: StateRefreshReport | None,
    ) -> RadarRuntimeCycleReport:
        with RadarRepository(self.db_path) as repository:
            cycle = repository.runtime_cycle(cycle_id)
        if cycle is None:
            raise RuntimeError(f"Runtime cycle {cycle_id} disappeared before it could be reported.")
        return RadarRuntimeCycleReport(
            cycle_id=cycle_id,
            mode=str(cycle["mode"]),
            status=str(cycle["status"]),
            phase=str(cycle["phase"]),
            started_at=str(cycle["started_at"]),
            finished_at=None if cycle.get("finished_at") is None else str(cycle["finished_at"]),
            discovery_run_id=None if cycle.get("discovery_run_id") is None else str(cycle["discovery_run_id"]),
            state_probed_count=int(cycle.get("state_probed_count") or 0),
            tracked_listings=int(cycle.get("tracked_listings") or 0),
            freshness_counts={
                "first-pass-only": int(cycle["freshness_counts"]["first-pass-only"]),
                "fresh-followup": int(cycle["freshness_counts"]["fresh-followup"]),
                "aging-followup": int(cycle["freshness_counts"]["aging-followup"]),
                "stale-followup": int(cycle["freshness_counts"]["stale-followup"]),
            },
            last_error=None if cycle.get("last_error") is None else str(cycle["last_error"]),
            config=dict(cycle.get("config") or {}),
            discovery_report=discovery_report,
            state_report=state_report,
        )
