from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import inspect
from pathlib import Path
import threading
import time
from typing import Callable, Sequence

from vinted_radar.db import DEFAULT_RUNTIME_LANE
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
class RadarRuntimeLaneProfile:
    lane_name: str
    options: RadarRuntimeOptions
    interval_seconds: float
    max_cycles: int | None = None
    benchmark_label: str | None = None


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
    lane_name: str = DEFAULT_RUNTIME_LANE
    benchmark_label: str | None = None
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
        self._control_plane_lock = threading.RLock()

    def _with_control_plane_repository(self, callback: Callable[[object], object]):
        if self.control_plane_repository is not None:
            with self._control_plane_lock:
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

    def _call_control_plane(self, method_name: str, /, **kwargs: object):
        def callback(repository: object):
            method = getattr(repository, method_name)
            try:
                signature = inspect.signature(method)
            except (TypeError, ValueError):
                filtered_kwargs = kwargs
            else:
                filtered_kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
            return method(**filtered_kwargs)

        return self._with_control_plane_repository(callback)

    def run_cycle(
        self,
        options: RadarRuntimeOptions,
        *,
        mode: str,
        interval_seconds: float | None = None,
        raise_on_error: bool = True,
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
    ) -> RadarRuntimeCycleReport:
        normalized_lane_name = _normalize_lane_name(lane_name)
        cycle_id = self._call_control_plane(
            "start_runtime_cycle",
            mode=mode,
            phase="starting",
            interval_seconds=interval_seconds,
            state_probe_limit=options.state_refresh_limit,
            config=options.as_config(),
            lane_name=normalized_lane_name,
            benchmark_label=benchmark_label,
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
            return self._build_report(
                cycle_id,
                lane_name=normalized_lane_name,
                benchmark_label=benchmark_label,
                discovery_report=discovery_report,
                state_report=state_report,
            )
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
                lane_name=normalized_lane_name,
                benchmark_label=benchmark_label,
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
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
        stop_requested: Callable[[], bool] | None = None,
        start_immediately: bool = False,
    ) -> list[RadarRuntimeCycleReport]:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be at least 1 when provided")

        normalized_lane_name = _normalize_lane_name(lane_name)
        reports: list[RadarRuntimeCycleReport] = []
        cycle_count = 0
        self._bootstrap_controller(
            options,
            interval_seconds=interval_seconds,
            lane_name=normalized_lane_name,
            benchmark_label=benchmark_label,
            start_immediately=start_immediately,
        )
        try:
            while max_cycles is None or cycle_count < max_cycles:
                if self._should_stop(stop_requested):
                    break
                cycle_window_start_at = self._wait_for_next_cycle_window(
                    options,
                    interval_seconds=interval_seconds,
                    lane_name=normalized_lane_name,
                    benchmark_label=benchmark_label,
                    stop_requested=stop_requested,
                )
                if cycle_window_start_at is None:
                    break

                report = self.run_cycle(
                    options,
                    mode="continuous",
                    interval_seconds=interval_seconds,
                    raise_on_error=not continue_on_error,
                    lane_name=normalized_lane_name,
                    benchmark_label=benchmark_label,
                )
                reports.append(report)
                cycle_count += 1

                should_continue = max_cycles is None or cycle_count < max_cycles
                if should_continue and not self._should_stop(stop_requested):
                    controller = self._call_control_plane(
                        "runtime_controller_state",
                        now=self._now_iso(),
                        lane_name=normalized_lane_name,
                    ) or {}
                    if controller.get("requested_action") == "pause":
                        self._pause_controller(
                            options,
                            interval_seconds=interval_seconds,
                            paused_at=self._now_iso(),
                            latest_cycle_id=report.cycle_id,
                            last_error=report.last_error if report.status == "failed" else None,
                            last_error_at=report.finished_at if report.status == "failed" else None,
                            lane_name=normalized_lane_name,
                            benchmark_label=benchmark_label,
                        )
                    else:
                        next_resume_at = self._iso_at(cycle_window_start_at + timedelta(seconds=interval_seconds))
                        self._schedule_controller(
                            options,
                            interval_seconds=interval_seconds,
                            next_resume_at=next_resume_at,
                            latest_cycle_id=report.cycle_id,
                            last_error=report.last_error if report.status == "failed" else None,
                            last_error_at=report.finished_at if report.status == "failed" else None,
                            lane_name=normalized_lane_name,
                            benchmark_label=benchmark_label,
                        )
                if on_cycle_complete is not None:
                    on_cycle_complete(report)
                if max_cycles is not None and cycle_count >= max_cycles:
                    break
        except KeyboardInterrupt:
            self._idle_controller(
                options,
                interval_seconds=interval_seconds,
                lane_name=normalized_lane_name,
                benchmark_label=benchmark_label,
            )
            raise

        self._idle_controller(
            options,
            interval_seconds=interval_seconds,
            lane_name=normalized_lane_name,
            benchmark_label=benchmark_label,
        )
        return reports

    def run_multi_lane_continuous(
        self,
        lane_profiles: Sequence[RadarRuntimeLaneProfile],
        *,
        continue_on_error: bool = True,
        on_cycle_complete: Callable[[RadarRuntimeCycleReport], None] | None = None,
        start_immediately: bool = False,
    ) -> dict[str, list[RadarRuntimeCycleReport]]:
        if not lane_profiles:
            raise ValueError("lane_profiles must contain at least one lane")

        normalized_names: list[str] = []
        for profile in lane_profiles:
            if profile.interval_seconds <= 0:
                raise ValueError(f"lane {profile.lane_name!r} interval_seconds must be greater than 0")
            if profile.max_cycles is not None and profile.max_cycles < 1:
                raise ValueError(f"lane {profile.lane_name!r} max_cycles must be at least 1 when provided")
            normalized_names.append(_normalize_lane_name(profile.lane_name))
        if len(set(normalized_names)) != len(normalized_names):
            raise ValueError("lane_profiles must use unique lane names")
        self._ensure_lane_aware_control_plane(lane_count=len(normalized_names))

        stop_event = threading.Event()
        results = {lane_name: [] for lane_name in normalized_names}
        results_lock = threading.Lock()
        worker_errors: list[BaseException] = []

        def handle_cycle_complete(report: RadarRuntimeCycleReport) -> None:
            with results_lock:
                results.setdefault(report.lane_name, []).append(report)
            if on_cycle_complete is not None:
                on_cycle_complete(report)

        def run_lane(profile: RadarRuntimeLaneProfile) -> None:
            try:
                self.run_continuous(
                    profile.options,
                    interval_seconds=profile.interval_seconds,
                    max_cycles=profile.max_cycles,
                    continue_on_error=continue_on_error,
                    on_cycle_complete=handle_cycle_complete,
                    lane_name=profile.lane_name,
                    benchmark_label=profile.benchmark_label,
                    stop_requested=stop_event.is_set,
                    start_immediately=start_immediately,
                )
            except BaseException as exc:  # noqa: BLE001
                with results_lock:
                    worker_errors.append(exc)
                stop_event.set()

        threads = [
            threading.Thread(
                target=run_lane,
                args=(profile,),
                name=f"runtime-lane-{_normalize_lane_name(profile.lane_name)}",
                daemon=True,
            )
            for profile in lane_profiles
        ]

        try:
            for thread in threads:
                thread.start()
            while any(thread.is_alive() for thread in threads):
                for thread in threads:
                    thread.join(timeout=0.05)
        except KeyboardInterrupt:
            stop_event.set()
            for thread in threads:
                thread.join()
            raise

        if worker_errors:
            raise worker_errors[0]
        return {lane_name: list(reports) for lane_name, reports in results.items()}

    def _bootstrap_controller(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
        start_immediately: bool = False,
    ) -> None:
        current_iso = self._now_iso()
        controller = self._call_control_plane("runtime_controller_state", now=current_iso, lane_name=lane_name) or {}
        latest_cycle_id = None if controller.get("latest_cycle_id") is None else str(controller["latest_cycle_id"])
        last_error = None if controller.get("last_error") is None else str(controller["last_error"])
        last_error_at = None if controller.get("last_error_at") is None else str(controller["last_error_at"])
        status = str(controller.get("status") or "idle")
        if start_immediately:
            self._schedule_controller(
                options,
                interval_seconds=interval_seconds,
                next_resume_at=current_iso,
                latest_cycle_id=latest_cycle_id,
                last_error=last_error,
                last_error_at=last_error_at,
                lane_name=lane_name,
                benchmark_label=benchmark_label,
            )
            return
        if status == "paused":
            self._pause_controller(
                options,
                interval_seconds=interval_seconds,
                paused_at=str(controller.get("paused_at") or current_iso),
                latest_cycle_id=latest_cycle_id,
                last_error=last_error,
                last_error_at=last_error_at,
                lane_name=lane_name,
                benchmark_label=benchmark_label,
            )
            return
        if status == "scheduled" and controller.get("next_resume_at"):
            self._schedule_controller(
                options,
                interval_seconds=interval_seconds,
                next_resume_at=str(controller["next_resume_at"]),
                latest_cycle_id=latest_cycle_id,
                last_error=last_error,
                last_error_at=last_error_at,
                lane_name=lane_name,
                benchmark_label=benchmark_label,
            )
            return
        self._schedule_controller(
            options,
            interval_seconds=interval_seconds,
            next_resume_at=current_iso,
            latest_cycle_id=latest_cycle_id,
            last_error=last_error,
            last_error_at=last_error_at,
            lane_name=lane_name,
            benchmark_label=benchmark_label,
        )

    def _schedule_controller(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        next_resume_at: str,
        latest_cycle_id: str | None,
        last_error: str | None,
        last_error_at: str | None,
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
    ) -> None:
        self._call_control_plane(
            "set_runtime_controller_state",
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
            latest_benchmark_label=benchmark_label,
            config=options.as_config(),
            lane_name=lane_name,
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
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
    ) -> None:
        self._call_control_plane(
            "set_runtime_controller_state",
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
            latest_benchmark_label=benchmark_label,
            config=options.as_config(),
            lane_name=lane_name,
        )

    def _idle_controller(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
    ) -> None:
        self._call_control_plane(
            "set_runtime_controller_state",
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
            latest_benchmark_label=benchmark_label,
            config=options.as_config(),
            lane_name=lane_name,
        )

    def _wait_for_next_cycle_window(
        self,
        options: RadarRuntimeOptions,
        *,
        interval_seconds: float,
        lane_name: str = DEFAULT_RUNTIME_LANE,
        benchmark_label: str | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> datetime | None:
        poll_seconds = self._poll_interval_seconds(interval_seconds)
        while True:
            if self._should_stop(stop_requested):
                return None
            current_dt = self.now_fn()
            current_iso = self._iso_at(current_dt)
            controller = self._call_control_plane("runtime_controller_state", now=current_iso, lane_name=lane_name)
            if controller is None:
                self._schedule_controller(
                    options,
                    interval_seconds=interval_seconds,
                    next_resume_at=current_iso,
                    latest_cycle_id=None,
                    last_error=None,
                    last_error_at=None,
                    lane_name=lane_name,
                    benchmark_label=benchmark_label,
                )
                return current_dt

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
                    lane_name=lane_name,
                    benchmark_label=benchmark_label,
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
                    lane_name=lane_name,
                    benchmark_label=benchmark_label,
                )
                return current_dt

            next_resume_at = controller.get("next_resume_at")
            if not next_resume_at:
                return current_dt

            scheduled_start_at = _parse_iso_datetime(str(next_resume_at))
            remaining = float(controller.get("next_resume_in_seconds") or 0.0)
            if remaining <= 0:
                return scheduled_start_at

            self._schedule_controller(
                options,
                interval_seconds=interval_seconds,
                next_resume_at=str(next_resume_at),
                latest_cycle_id=latest_cycle_id,
                last_error=last_error,
                last_error_at=last_error_at,
                lane_name=lane_name,
                benchmark_label=benchmark_label,
            )
            self.sleep_fn(min(poll_seconds, remaining))

    def _ensure_lane_aware_control_plane(self, *, lane_count: int) -> None:
        if lane_count <= 1:
            return
        required_methods = (
            "set_runtime_controller_state",
            "runtime_controller_state",
            "request_runtime_pause",
            "request_runtime_resume",
        )
        missing = [method_name for method_name in required_methods if not self._control_plane_method_supports_lane_name(method_name)]
        if missing:
            missing_methods = ", ".join(missing)
            raise RuntimeError(
                f"Multi-lane orchestration requires a lane-aware control plane repository; missing lane_name support on: {missing_methods}"
            )

    def _control_plane_method_supports_lane_name(self, method_name: str) -> bool:
        if self.control_plane_repository is None:
            return True
        method = getattr(self.control_plane_repository, method_name, None)
        if method is None:
            return False
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return False
        return "lane_name" in signature.parameters

    def _should_stop(self, stop_requested: Callable[[], bool] | None) -> bool:
        return False if stop_requested is None else bool(stop_requested())

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
        lane_name: str,
        benchmark_label: str | None,
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
        return self._build_report(
            cycle_id,
            lane_name=lane_name,
            benchmark_label=benchmark_label,
            discovery_report=discovery_report,
            state_report=state_report,
        )

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
        lane_name: str,
        benchmark_label: str | None,
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
            lane_name=str(cycle.get("lane_name") or lane_name),
            benchmark_label=(
                benchmark_label
                if "benchmark_label" not in cycle or cycle.get("benchmark_label") is None
                else str(cycle.get("benchmark_label"))
            ),
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


def _normalize_lane_name(lane_name: object) -> str:
    if lane_name is None:
        return DEFAULT_RUNTIME_LANE
    normalized = str(lane_name).strip()
    return normalized or DEFAULT_RUNTIME_LANE


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
