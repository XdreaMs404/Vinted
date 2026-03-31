from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vinted_radar.query.detail_clickhouse import load_clickhouse_listing_history, load_clickhouse_state_inputs
from vinted_radar.query.explorer_clickhouse import (
    build_comparison_module,
    build_explorer_filter_options,
    build_explorer_snapshot,
)
from vinted_radar.query.feature_marts import (
    fetch_clickhouse_listing_day_mart,
    fetch_clickhouse_price_change_mart,
    fetch_clickhouse_segment_day_mart,
    fetch_clickhouse_state_transition_mart,
    load_clickhouse_evidence_packs,
    load_clickhouse_feature_marts_export,
)
from vinted_radar.state_machine import STATE_ORDER, evaluate_listing_state

_PRICE_BAND_LABELS = {
    "under_20_eur": "< 20 €",
    "20_to_39_eur": "20–39 €",
    "40_plus_eur": "40 € et plus",
    "unknown": "Prix indisponible",
}
_STATE_LABELS = {
    "active": "Actif",
    "sold_observed": "Vendu observé",
    "sold_probable": "Vendu probable",
    "unavailable_non_conclusive": "Indisponible",
    "deleted": "Supprimée",
    "unknown": "Inconnu",
}
_FULL_SIGNAL_COMPLETENESS = 7
_HIGH_SIGNAL_COMPLETENESS = 5
_DEFAULT_OVERVIEW_COMPARISON_LIMIT = 6
_DEFAULT_OVERVIEW_SUPPORT_THRESHOLD = 3


@dataclass(slots=True)
class ClickHouseProductQueryAdapter:
    repository: Any
    clickhouse_client: object
    database: str
    control_plane_repository: Any | None = None
    overview_snapshot_source: str = "clickhouse.overview_snapshot"
    _state_input_cache: dict[tuple[str | None, int | None], list[dict[str, object]]] = field(default_factory=dict)
    _evaluated_cache: dict[str | None, list[dict[str, object]]] = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return Path(self.repository.db_path)

    @property
    def connection(self):
        return self.repository.connection

    def coverage_summary(self, run_id: str | None = None) -> dict[str, object] | None:
        control_plane_repository = self._control_plane_repository("coverage_summary")
        if control_plane_repository is not None:
            return control_plane_repository.coverage_summary(run_id=run_id)
        return self.repository.coverage_summary(run_id=run_id)

    def runtime_status(self, *, limit: int = 10, now: str | None = None) -> dict[str, object]:
        control_plane_repository = self._control_plane_repository("runtime_status")
        if control_plane_repository is not None:
            return control_plane_repository.runtime_status(limit=limit, now=now)
        return self.repository.runtime_status(limit=limit, now=now)

    def listing_state_inputs(self, *, now: str | None = None, listing_id: int | None = None) -> list[dict[str, object]]:
        cache_key = (_cache_key(now), None if listing_id is None else int(listing_id))
        cached = self._state_input_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]
        rows = load_clickhouse_state_inputs(
            self.clickhouse_client,
            database=self.database,
            now=now,
            listing_id=listing_id,
        )
        stored = [dict(item) for item in rows]
        self._state_input_cache[cache_key] = stored
        return [dict(item) for item in stored]

    def listing_price_context_peer_prices(
        self,
        *,
        primary_catalog_id: int | None = None,
        root_title: str | None = None,
        brand: str | None = None,
        condition_label: str | None = None,
    ) -> list[int]:
        from vinted_radar.query.detail_clickhouse import fetch_clickhouse_price_context_peer_prices

        return fetch_clickhouse_price_context_peer_prices(
            self.clickhouse_client,
            database=self.database,
            primary_catalog_id=primary_catalog_id,
            root_title=root_title,
            brand=brand,
            condition_label=condition_label,
        )

    def listing_history(self, listing_id: int, *, now: str | None = None, limit: int = 20) -> dict[str, object] | None:
        return load_clickhouse_listing_history(
            self.clickhouse_client,
            database=self.database,
            listing_id=listing_id,
            now=now,
            limit=limit,
        )

    def listing_day_mart(
        self,
        *,
        listing_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return fetch_clickhouse_listing_day_mart(
            self.clickhouse_client,
            database=self.database,
            listing_ids=listing_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def segment_day_mart(
        self,
        *,
        segment_lens: str = "all",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return fetch_clickhouse_segment_day_mart(
            self.clickhouse_client,
            database=self.database,
            segment_lens=segment_lens,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def price_change_mart(
        self,
        *,
        listing_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return fetch_clickhouse_price_change_mart(
            self.clickhouse_client,
            database=self.database,
            listing_ids=listing_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def state_transition_mart(
        self,
        *,
        listing_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return fetch_clickhouse_state_transition_mart(
            self.clickhouse_client,
            database=self.database,
            listing_ids=listing_ids,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def evidence_packs(
        self,
        *,
        listing_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        now: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        return load_clickhouse_evidence_packs(
            self.clickhouse_client,
            database=self.database,
            listing_ids=listing_ids,
            start_date=start_date,
            end_date=end_date,
            now=now,
            limit=limit,
        )

    def feature_marts_export(
        self,
        *,
        listing_ids: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        segment_lens: str = "all",
        now: str | None = None,
        limit: int = 25,
    ) -> dict[str, object]:
        return load_clickhouse_feature_marts_export(
            self.clickhouse_client,
            database=self.database,
            listing_ids=listing_ids,
            start_date=start_date,
            end_date=end_date,
            segment_lens=segment_lens,
            now=now,
            limit=limit,
        )

    def explorer_filter_options(self, *, now: str | None = None) -> dict[str, list[dict[str, object]] | int]:
        return build_explorer_filter_options(self._evaluated_items(now=now))

    def explorer_snapshot(
        self,
        *,
        root: str | None = None,
        catalog_id: int | None = None,
        brand: str | None = None,
        condition: str | None = None,
        state: str | None = None,
        price_band: str | None = None,
        query: str | None = None,
        sort: str = "last_seen_desc",
        page: int = 1,
        page_size: int = 50,
        comparison_limit: int = _DEFAULT_OVERVIEW_COMPARISON_LIMIT,
        support_threshold: int = _DEFAULT_OVERVIEW_SUPPORT_THRESHOLD,
        now: str | None = None,
    ) -> dict[str, object]:
        return build_explorer_snapshot(
            self._evaluated_items(now=now),
            root=root,
            catalog_id=catalog_id,
            brand=brand,
            condition=condition,
            state=state,
            price_band=price_band,
            query=query,
            sort=sort,
            page=page,
            page_size=page_size,
            comparison_limit=comparison_limit,
            support_threshold=support_threshold,
        )

    def listing_explorer_page(
        self,
        *,
        root: str | None = None,
        catalog_id: int | None = None,
        brand: str | None = None,
        condition: str | None = None,
        state: str | None = None,
        price_band: str | None = None,
        query: str | None = None,
        sort: str = "last_seen_desc",
        page: int = 1,
        page_size: int = 50,
        now: str | None = None,
    ) -> dict[str, object]:
        snapshot = build_explorer_snapshot(
            self._evaluated_items(now=now),
            root=root,
            catalog_id=catalog_id,
            brand=brand,
            condition=condition,
            state=state,
            price_band=price_band,
            query=query,
            sort=sort,
            page=page,
            page_size=page_size,
            comparison_limit=_DEFAULT_OVERVIEW_COMPARISON_LIMIT,
            support_threshold=_DEFAULT_OVERVIEW_SUPPORT_THRESHOLD,
        )
        return snapshot["page"]

    def overview_snapshot(
        self,
        *,
        now: str | None = None,
        comparison_limit: int = _DEFAULT_OVERVIEW_COMPARISON_LIMIT,
        support_threshold: int = _DEFAULT_OVERVIEW_SUPPORT_THRESHOLD,
    ) -> dict[str, object]:
        generated_at = _generated_at(now)
        items = self._evaluated_items(now=generated_at)
        bounded_limit = max(int(comparison_limit), 1)
        bounded_support_threshold = max(int(support_threshold), 1)

        coverage = self.coverage_summary()
        runtime = self.runtime_status(limit=5, now=generated_at)
        controller = runtime.get("controller") if isinstance(runtime, dict) else None
        latest_cycle = runtime.get("latest_cycle") if isinstance(runtime, dict) else None
        recent_failures = [] if coverage is None else list(coverage.get("failures") or [])

        comparisons = {
            "category": build_comparison_module(
                items,
                lens="category",
                title="Catégories",
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            ),
            "brand": build_comparison_module(
                items,
                lens="brand",
                title="Marques",
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            ),
            "price_band": build_comparison_module(
                items,
                lens="price_band",
                title="Tranches de prix",
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            ),
            "condition": build_comparison_module(
                items,
                lens="condition",
                title="États",
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            ),
            "sold_state": build_comparison_module(
                items,
                lens="sold_state",
                title="Statut de vente",
                limit=bounded_limit,
                support_threshold=bounded_support_threshold,
            ),
        }

        latest_listing_seen_at = max((item.get("last_seen_at") for item in items if item.get("last_seen_at")), default=None)
        latest_successful_scan_at = max((item.get("latest_primary_scan_at") for item in items if item.get("latest_primary_scan_at")), default=None)

        return {
            "generated_at": generated_at,
            "db_path": str(self.db_path),
            "summary": {
                "inventory": {
                    "tracked_listings": len(items),
                    "sold_like_count": sum(1 for item in items if bool(item.get("sold_like"))),
                    "comparison_support_threshold": bounded_support_threshold,
                    "state_counts": {
                        state_code: sum(1 for item in items if item.get("state_code") == state_code)
                        for state_code in STATE_ORDER
                    },
                },
                "honesty": {
                    "observed_state_count": sum(1 for item in items if item.get("basis_kind") == "observed"),
                    "inferred_state_count": sum(1 for item in items if item.get("basis_kind") == "inferred"),
                    "unknown_state_count": sum(1 for item in items if item.get("basis_kind") == "unknown"),
                    "partial_signal_count": sum(int(item.get("partial_signal") or 0) for item in items),
                    "thin_signal_count": sum(int(item.get("thin_signal") or 0) for item in items),
                    "estimated_publication_count": sum(int(item.get("has_estimated_publication") or 0) for item in items),
                    "missing_estimated_publication_count": sum(1 for item in items if not bool(item.get("has_estimated_publication"))),
                    "confidence_counts": {
                        "high": sum(1 for item in items if item.get("confidence_label") == "high"),
                        "medium": sum(1 for item in items if item.get("confidence_label") == "medium"),
                        "low": sum(1 for item in items if item.get("confidence_label") == "low"),
                    },
                },
                "freshness": {
                    "latest_listing_seen_at": latest_listing_seen_at,
                    "latest_successful_scan_at": latest_successful_scan_at,
                    "latest_run_id": None if coverage is None else coverage["run"].get("run_id"),
                    "latest_run_started_at": None if coverage is None else coverage["run"].get("started_at"),
                    "latest_run_finished_at": None if coverage is None else coverage["run"].get("finished_at"),
                    "current_runtime_status": runtime.get("status") if isinstance(runtime, dict) else None,
                    "current_runtime_phase": runtime.get("phase") if isinstance(runtime, dict) else None,
                    "current_runtime_updated_at": runtime.get("updated_at") if isinstance(runtime, dict) else None,
                    "current_runtime_next_resume_at": runtime.get("next_resume_at") if isinstance(runtime, dict) else None,
                    "current_runtime_paused_at": runtime.get("paused_at") if isinstance(runtime, dict) else None,
                    "current_runtime_heartbeat_stale": False if controller is None else bool((controller.get("heartbeat") or {}).get("is_stale")),
                    "latest_runtime_cycle_status": None if latest_cycle is None else latest_cycle.get("status"),
                    "latest_runtime_cycle_started_at": None if latest_cycle is None else latest_cycle.get("started_at"),
                    "acquisition_status": None if not isinstance(runtime, dict) else (runtime.get("acquisition") or {}).get("status"),
                    "acquisition_reasons": [] if not isinstance(runtime, dict) else list((runtime.get("acquisition") or {}).get("reasons") or []),
                    "recent_probe_issue_count": 0 if not isinstance(runtime, dict) else int(((runtime.get("acquisition") or {}).get("latest_state_refresh_summary") or {}).get("degraded_probe_count") or 0),
                    "recent_inconclusive_probe_count": 0 if not isinstance(runtime, dict) else int(((runtime.get("acquisition") or {}).get("latest_state_refresh_summary") or {}).get("inconclusive_probe_count") or 0),
                    "recent_probe_issues": [] if not isinstance(runtime, dict) else list((runtime.get("acquisition") or {}).get("probe_issue_examples") or []),
                    "recent_acquisition_failure_count": len(recent_failures),
                    "recent_acquisition_failures": recent_failures,
                },
            },
            "comparisons": comparisons,
            "coverage": coverage,
            "runtime": runtime,
        }

    def _evaluated_items(self, *, now: str | None = None) -> list[dict[str, object]]:
        cache_key = _cache_key(now)
        cached = self._evaluated_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        generated_at = _generated_at(now)
        inputs = self.listing_state_inputs(now=generated_at)
        evaluated: list[dict[str, object]] = []
        for row in inputs:
            item = evaluate_listing_state(dict(row), now=generated_at)
            item.update(_presentational_fields(item))
            evaluated.append(item)
        stored = [dict(item) for item in evaluated]
        self._evaluated_cache[cache_key] = stored
        return [dict(item) for item in stored]

    def _control_plane_repository(self, method_name: str):
        repository = self.control_plane_repository
        if repository is None:
            return None
        method = getattr(repository, method_name, None)
        if not callable(method):
            return None
        return repository


def _presentational_fields(item: dict[str, object]) -> dict[str, object]:
    price_amount_cents = item.get("price_amount_cents")
    if price_amount_cents is None:
        price_band_code = "unknown"
        price_band_label = _PRICE_BAND_LABELS[price_band_code]
        price_band_sort_order = 4
    else:
        amount = int(price_amount_cents)
        if amount < 2000:
            price_band_code = "under_20_eur"
            price_band_sort_order = 1
        elif amount < 4000:
            price_band_code = "20_to_39_eur"
            price_band_sort_order = 2
        else:
            price_band_code = "40_plus_eur"
            price_band_sort_order = 3
        price_band_label = _PRICE_BAND_LABELS[price_band_code]

    state_code = str(item.get("state_code") or "unknown")
    return {
        "price_band_code": price_band_code,
        "price_band_label": price_band_label,
        "price_band_sort_order": price_band_sort_order,
        "state_label": _STATE_LABELS.get(state_code, state_code),
        "state_sort_order": STATE_ORDER.index(state_code) + 1 if state_code in STATE_ORDER else len(STATE_ORDER) + 1,
        "sold_like": state_code in {"sold_observed", "sold_probable"},
        "partial_signal": 1 if int(item.get("signal_completeness") or 0) < _FULL_SIGNAL_COMPLETENESS else 0,
        "thin_signal": 1 if int(item.get("signal_completeness") or 0) < _HIGH_SIGNAL_COMPLETENESS else 0,
        "has_estimated_publication": 1 if item.get("created_at_ts") is not None else 0,
    }


def _generated_at(now: str | None) -> str:
    if now is None:
        return datetime.now(UTC).replace(microsecond=0).isoformat()
    return datetime.fromisoformat(now).replace(microsecond=0).isoformat()


def _cache_key(now: str | None) -> str | None:
    if now is None:
        return None
    return datetime.fromisoformat(now).replace(microsecond=0).isoformat()


__all__ = ["ClickHouseProductQueryAdapter"]
