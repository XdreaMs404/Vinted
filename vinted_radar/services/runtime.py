from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import time
from typing import Callable

from vinted_radar.repository import RadarRepository
from vinted_radar.services.discovery import DiscoveryOptions, DiscoveryRunReport, build_default_service
from vinted_radar.services.state_refresh import StateRefreshReport, build_default_state_refresh_service


@dataclass(frozen=True, slots=True)
class RadarRuntimeOptions:
    page_limit: int = 5
    max_leaf_categories: int | None = None
    root_scope: str = "both"
    request_delay: float = 3.0
    timeout_seconds: float = 20.0
    state_refresh_limit: int = 10
    concurrency: int = 1
    min_price: float = 30.0
    max_price: float = 0.0
    target_catalogs: tuple[int, ...] = ()
    target_brands: tuple[str, ...] = ()
    proxies: tuple[str, ...] = ()

    def as_config(self) -> dict[str, object]:
        return {
            "page_limit": self.page_limit,
            "max_leaf_categories": self.max_leaf_categories,
            "root_scope": self.root_scope,
            "request_delay": self.request_delay,
            "timeout_seconds": self.timeout_seconds,
            "state_refresh_limit": self.state_refresh_limit,
            "concurrency": self.concurrency,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "target_catalogs": list(self.target_catalogs),
            "target_brands": list(self.target_brands),
            "transport_mode": "proxy-pool" if self.proxies else "direct",
            "proxy_pool_size": len(self.proxies),
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
    state_refresh_summary: dict[str, object] | None = None
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
        now_fn: Callable[[], datetime] | None = None,
        control_plane_repository: object | None = None,
        mutable_truth_sync: Callable[[], None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.discovery_service_factory = discovery_service_factory
        self.state_refresh_service_factory = state_refresh_service_factory
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn or (lambda: datetime.now(UTC))
        self.control_plane_repository = control_plane_repository
        self.mutable_truth_sync = mutable_truth_sync

    def _with_control_plane_repository(self, callback: Callable[[object], object]):
        if self.control_plane_repository is not None:
            return callback(self.control_plane_repository)
        with RadarRepository(self.db_path) as repository:
            return callback(repository)

    def close(self) -> None:
        if self.control_plane_repository is None:
            return
        close = getattr(self.control_plane_repository, "close", None)
        if callable(close):
            close()

    def _sync_mutable_truth(self) -> None:
        if self.mutable_truth_sync is not None:
            self.mutable_truth_sync()

    def run_cycle(
        self,
        options: RadarRuntimeOptions,
        *,
        mode: str,
        interval_seconds: float | None = None,
        raise_on_error: bool = True,
    ) -> RadarRuntimeCycleReport:
        cycle_id = self._with_control_plane_repository(
            lambda repository: repository.start_runtime_cycle(
                mode=mode,
                phase="starting",
                interval_seconds=interval_seconds,
                state_probe_limit=options.state_refresh_limit,
                config=options.as_config(),
            )
        )
        cycle_row = self._with_control_plane_repository(lambda repository: repository.runtime_cycle(cycle_id))
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
                proxies=list(options.proxies) or None,
            )
            try:
                discovery_report = discovery_service.run(
                    DiscoveryOptions(
                        page_limit=options.page_limit,
                        max_leaf_categories=options.max_leaf_categories,
                        root_scope=options.root_scope,
                        request_delay=options.request_delay,
                        concurrency=options.concurrency,
                        min_price=options.min_price,
                        max_price=options.max_price,
                        target_catalogs=options.target_catalogs,
                        target_brands=options.target_brands,
                    )
                )
            finally:
                _close_service(discovery_service)
            self._sync_mutable_truth()

            current_phase = "state_refresh"
            self._update_phase(cycle_id, current_phase)
            state_refresh_service = self.state_refresh_service_factory(
                db_path=str(self.db_path),
                timeout_seconds=options.timeout_seconds,
                request_delay=options.request_delay,
                proxies=list(options.proxies) or None,
            )
            try:
                state_report = state_refresh_service.refresh(limit=options.state_refresh_limit, include_state_summary=False)
            finally:
                _close_service(state_refresh_service)
            self._sync_mutable_truth()

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
                state_refresh_summary=state_report.probe_summary,
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
                state_refresh_summary=None if state_report is None else state_report.probe_summary,
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
        self._schedule_controller(
            options,
            interval_seconds=interval_seconds,
            next_resume_at=self._now_iso(),
            latest_cycle_id=None,
            last_error=None,
            last_error_at=None,
        )
        try:
            while max_cycles is None or cycle_count < max_cycles:
                self._wait_for_next_cycle_window(options, interval_seconds=interval_seconds)
                report = self.run_cycle(
                    options,
                    mode="continuous",
                    interval_seconds=interval_seconds,
                    raise_on_error=not continue_on_error,
                )
                reports.append(report)
                cycle_count += 1
                if max_cycles is None or cycle_count < max_cycles:
                    controller = self._with_control_plane_repository(
                        lambda repository: repository.runtime_controller_state(now=self._now_iso()) or {}
                    )
                    if controller.get("requested_action") == "pause":
                        self._pause_controller(
                            options,
                            interval_seconds=interval_seconds,
                            paused_at=self._now_iso(),
                            latest_cycle_id=report.cycle_id,
                            last_error=report.last_error if report.status == "failed" else None,
                            last_error_at=report.finished_at if report.status == "failed" else None,
                        )
                    else:
                        next_resume_at = self._iso_at(self.now_fn() + timedelta(seconds=interval_seconds))
                        self._schedule_controller(
                            options,
                            interval_seconds=interval_seconds,
                            next_resume_at=next_resume_at,
                            latest_cycle_id=report.cycle_id,
                            last_error=report.last_error if report.status == "failed" else None,
                            last_error_at=report.finished_at if report.status == "failed" else None,
                        )
                if on_cycle_complete is not None:
                    on_cycle_complete(report)
                if max_cycles is not None and cycle_count >= max_cycles:
                    break
        except KeyboardInterrupt:
            self._idle_controller(options, interval_seconds=interval_seconds)
            raise

        self._idle_controller(options, interval_seconds=interval_seconds)
        return reports

    def _schedule_controller(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        next_resume_at: str,
        latest_cycle_id: str | None,
        last_error: str | None,
        last_error_at: str | None,
    ) -> None:
        self._with_control_plane_repository(
            lambda repository: repository.set_runtime_controller_state(
                status="scheduled",
                phase="waiting",
                mode="continuous",
                active_cycle_id=None,
                latest_cycle_id=latest_cycle_id,
                interval_seconds=interval_seconds,
                updated_at=self._now_iso(),
                paused_at=None,
                next_resume_at=next_resume_at,
                last_error=last_error,
                last_error_at=last_error_at,
                requested_action="none",
                requested_at=None,
                config=options.as_config(),
            )
        )

    def _pause_controller(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        paused_at: str,
        latest_cycle_id: str | None,
        last_error: str | None,
        last_error_at: str | None,
    ) -> None:
        self._with_control_plane_repository(
            lambda repository: repository.set_runtime_controller_state(
                status="paused",
                phase="paused",
                mode="continuous",
                active_cycle_id=None,
                latest_cycle_id=latest_cycle_id,
                interval_seconds=interval_seconds,
                updated_at=self._now_iso(),
                paused_at=paused_at,
                next_resume_at=None,
                last_error=last_error,
                last_error_at=last_error_at,
                requested_action="none",
                requested_at=None,
                config=options.as_config(),
            )
        )

    def _idle_controller(self, options: RadarRuntimeOptions, *, interval_seconds: float) -> None:
        self._with_control_plane_repository(
            lambda repository: repository.set_runtime_controller_state(
                status="idle",
                phase="idle",
                mode="continuous",
                active_cycle_id=None,
                interval_seconds=interval_seconds,
                updated_at=self._now_iso(),
                paused_at=None,
                next_resume_at=None,
                requested_action="none",
                requested_at=None,
                config=options.as_config(),
            )
        )

    def _wait_for_next_cycle_window(self, options: RadarRuntimeOptions, *, interval_seconds: float) -> None:
        poll_seconds = self._poll_interval_seconds(interval_seconds)
        while True:
            current_iso = self._now_iso()
            controller = self._with_control_plane_repository(
                lambda repository: repository.runtime_controller_state(now=current_iso)
            )
            if controller is None:
                self._schedule_controller(
                    options,
                    interval_seconds=interval_seconds,
                    next_resume_at=current_iso,
                    latest_cycle_id=None,
                    last_error=None,
                    last_error_at=None,
                )
                return

            status = str(controller.get("status") or "idle")
            latest_cycle_id = None if controller.get("latest_cycle_id") is None else str(controller["latest_cycle_id"])
            last_error = None if controller.get("last_error") is None else str(controller["last_error"])
            last_error_at = None if controller.get("last_error_at") is None else str(controller["last_error_at"])

            if status == "paused":
                self._pause_controller(
                    options,
                    interval_seconds=interval_seconds,
                    paused_at=str(controller.get("paused_at") or current_iso),
                    latest_cycle_id=latest_cycle_id,
                    last_error=last_error,
                    last_error_at=last_error_at,
                )
                self.sleep_fn(poll_seconds)
                continue

            if status != "scheduled":
                self._schedule_controller(
                    options,
                    interval_seconds=interval_seconds,
                    next_resume_at=current_iso,
                    latest_cycle_id=latest_cycle_id,
                    last_error=last_error,
                    last_error_at=last_error_at,
                )
                return

            next_resume_at = controller.get("next_resume_at")
            if not next_resume_at:
                return

            remaining = float(controller.get("next_resume_in_seconds") or 0.0)
            if remaining <= 0:
                return

            self._schedule_controller(
                options,
                interval_seconds=interval_seconds,
                next_resume_at=str(next_resume_at),
                latest_cycle_id=latest_cycle_id,
                last_error=last_error,
                last_error_at=last_error_at,
            )
            self.sleep_fn(min(poll_seconds, remaining))

    def _poll_interval_seconds(self, interval_seconds: float) -> float:
        return min(max(interval_seconds / 10.0, 0.25), 1.0)

    def _now_iso(self) -> str:
        return self._iso_at(self.now_fn())

    def _iso_at(self, value: datetime) -> str:
        return value.astimezone(UTC).replace(microsecond=0).isoformat()

    def _update_phase(self, cycle_id: str, phase: str) -> None:
        self._with_control_plane_repository(lambda repository: repository.update_runtime_cycle_phase(cycle_id, phase=phase))

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
        state_refresh_summary: dict[str, object] | None,
    ) -> None:
        self._with_control_plane_repository(
            lambda repository: repository.complete_runtime_cycle(
                cycle_id,
                status=status,
                phase=phase,
                discovery_run_id=discovery_run_id,
                state_probed_count=state_probed_count,
                tracked_listings=tracked_listings,
                freshness_counts=freshness_counts,
                last_error=last_error,
                state_refresh_summary=state_refresh_summary,
            )
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
            state_refresh_summary=None if state_report is None else state_report.probe_summary,
        )
        return self._build_report(cycle_id, discovery_report=discovery_report, state_report=state_report)

    def _runtime_snapshot(self) -> tuple[int, dict[str, int]]:
        try:
            with RadarRepository(self.db_path) as repository:
                freshness = repository.freshness_summary()
                tracked_listings = int(freshness["overall"].get("tracked_listings") or 0)
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
        cycle = self._with_control_plane_repository(lambda repository: repository.runtime_cycle(cycle_id))
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
            state_refresh_summary=dict(cycle.get("state_refresh_summary") or {}),
            discovery_report=discovery_report,
            state_report=state_report,
        )


def _close_service(service: object) -> None:
    close = getattr(service, "close", None)
    if callable(close):
        close()
        return
    repository = getattr(service, "repository", None)
    if repository is None:
        return
    repository_close = getattr(repository, "close", None)
    if callable(repository_close):
        repository_close()
