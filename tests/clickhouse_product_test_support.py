from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any


class ScriptedClickHouseClient:
    def __init__(
        self,
        *,
        state_rows: list[dict[str, Any]],
        timeline_rows: dict[int, list[dict[str, Any]]],
        peer_price_rows: dict[tuple[int | None, str | None, str | None, str | None], list[int]],
    ) -> None:
        self.state_rows = [dict(row) for row in state_rows]
        self.timeline_rows = {int(key): [dict(row) for row in value] for key, value in timeline_rows.items()}
        self.peer_price_rows = {key: [int(item) for item in value] for key, value in peer_price_rows.items()}
        self.queries: list[str] = []

    def query(self, sql: str):
        self.queries.append(sql)
        if "clickhouse-query: state-inputs" in sql:
            match = re.search(r"listing_id=([a-zA-Z0-9_-]+)", sql)
            marker = None if match is None else match.group(1)
            if marker in {None, "all"}:
                rows = self.state_rows
            else:
                listing_id = int(marker)
                rows = [row for row in self.state_rows if int(row["listing_id"]) == listing_id]
            return SimpleNamespace(result_rows=[dict(row) for row in rows])

        if "clickhouse-query: timeline" in sql:
            listing_id = int(re.search(r"listing_id=(\d+)", sql).group(1))
            limit_match = re.search(r"limit=(\d+)", sql)
            limit = None if limit_match is None else int(limit_match.group(1))
            rows = self.timeline_rows.get(listing_id, [])
            if limit is not None:
                rows = rows[:limit]
            return SimpleNamespace(result_rows=[dict(row) for row in rows])

        if "clickhouse-query: peer-prices" in sql:
            def _marker(name: str) -> str | None:
                match = re.search(rf"{name}=([^ */]+)", sql)
                if match is None:
                    return None
                value = match.group(1)
                return None if value == "*" else value

            catalog = _marker("primary_catalog_id")
            key = (
                None if catalog is None else int(catalog),
                _marker("root_title"),
                _marker("brand"),
                _marker("condition_label"),
            )
            prices = self.peer_price_rows.get(key, [])
            return SimpleNamespace(result_rows=[{"price_amount_cents": int(price)} for price in prices])

        raise AssertionError(f"Unexpected ClickHouse SQL: {sql}")

    def close(self) -> None:
        return None



def make_clickhouse_product_client() -> ScriptedClickHouseClient:
    state_rows = [
        {
            "listing_id": 9003,
            "observation_count": 1,
            "total_sightings": 1,
            "first_seen_at": "2026-03-19T10:05:00+00:00",
            "last_seen_at": "2026-03-19T10:05:00+00:00",
            "average_revisit_hours": None,
            "last_observed_run_id": "run-3",
            "canonical_url": "https://www.vinted.fr/items/9003-new",
            "source_url": "https://www.vinted.fr/items/9003-new?referrer=catalog",
            "title": "New robe",
            "brand": "Maje",
            "size_label": "L",
            "condition_label": "Neuf",
            "price_amount_cents": 4200,
            "price_currency": "€",
            "total_price_amount_cents": 4550,
            "total_price_currency": "€",
            "image_url": "https://images/9003.webp",
            "favourite_count": 41,
            "view_count": 650,
            "user_id": 43,
            "user_login": "claire",
            "user_profile_url": "https://www.vinted.fr/member/43",
            "created_at_ts": 1711188000,
            "root_title": "Femmes",
            "primary_catalog_id": 2001,
            "primary_root_catalog_id": 1904,
            "primary_catalog_path": "Femmes > Robes",
            "latest_primary_scan_run_id": "run-3",
            "latest_primary_scan_at": "2026-03-19T10:05:00+00:00",
            "follow_up_miss_count": 0,
            "latest_follow_up_miss_at": None,
            "latest_probe_probed_at": None,
            "latest_probe_requested_url": None,
            "latest_probe_final_url": None,
            "latest_probe_response_status": None,
            "latest_probe_outcome": None,
            "latest_probe_detail_json": None,
            "latest_probe_error_message": None,
        },
        {
            "listing_id": 9001,
            "observation_count": 3,
            "total_sightings": 3,
            "first_seen_at": "2026-03-17T10:05:00+00:00",
            "last_seen_at": "2026-03-19T10:05:00+00:00",
            "average_revisit_hours": 24.0,
            "last_observed_run_id": "run-3",
            "canonical_url": "https://www.vinted.fr/items/9001-active",
            "source_url": "https://www.vinted.fr/items/9001-active?referrer=catalog",
            "title": "Active robe",
            "brand": "Zara",
            "size_label": "M",
            "condition_label": "Très bon état",
            "price_amount_cents": 1500,
            "price_currency": "€",
            "total_price_amount_cents": 1650,
            "total_price_currency": "€",
            "image_url": "https://images/9001.webp",
            "favourite_count": 11,
            "view_count": 120,
            "user_id": 41,
            "user_login": "alice",
            "user_profile_url": "https://www.vinted.fr/member/41",
            "created_at_ts": 1711101600,
            "root_title": "Femmes",
            "primary_catalog_id": 2001,
            "primary_root_catalog_id": 1904,
            "primary_catalog_path": "Femmes > Robes",
            "latest_primary_scan_run_id": "run-3",
            "latest_primary_scan_at": "2026-03-19T10:05:00+00:00",
            "follow_up_miss_count": 0,
            "latest_follow_up_miss_at": None,
            "latest_probe_probed_at": "2026-03-19T11:00:00+00:00",
            "latest_probe_requested_url": "https://www.vinted.fr/items/9001-active",
            "latest_probe_final_url": "https://www.vinted.fr/items/9001-active",
            "latest_probe_response_status": 200,
            "latest_probe_outcome": "active",
            "latest_probe_detail_json": json.dumps({"reason": "buy_signal_open", "response_status": 200}),
            "latest_probe_error_message": None,
        },
        {
            "listing_id": 9004,
            "observation_count": 1,
            "total_sightings": 1,
            "first_seen_at": "2026-03-18T10:05:00+00:00",
            "last_seen_at": "2026-03-18T10:05:00+00:00",
            "average_revisit_hours": None,
            "last_observed_run_id": "run-2",
            "canonical_url": "https://www.vinted.fr/items/9004-deleted",
            "source_url": "https://www.vinted.fr/items/9004-deleted?referrer=catalog",
            "title": "Deleted robe",
            "brand": "Mango",
            "size_label": "L",
            "condition_label": "Neuf",
            "price_amount_cents": 2000,
            "price_currency": "€",
            "total_price_amount_cents": 2200,
            "total_price_currency": "€",
            "image_url": "https://images/9004.webp",
            "favourite_count": None,
            "view_count": None,
            "user_id": None,
            "user_login": None,
            "user_profile_url": None,
            "created_at_ts": None,
            "root_title": "Femmes",
            "primary_catalog_id": 2001,
            "primary_root_catalog_id": 1904,
            "primary_catalog_path": "Femmes > Robes",
            "latest_primary_scan_run_id": "run-3",
            "latest_primary_scan_at": "2026-03-19T10:05:00+00:00",
            "follow_up_miss_count": 1,
            "latest_follow_up_miss_at": "2026-03-19T10:05:00+00:00",
            "latest_probe_probed_at": "2026-03-19T11:10:00+00:00",
            "latest_probe_requested_url": "https://www.vinted.fr/items/9004-deleted",
            "latest_probe_final_url": "https://www.vinted.fr/items/9004-deleted",
            "latest_probe_response_status": 404,
            "latest_probe_outcome": "deleted",
            "latest_probe_detail_json": json.dumps({"reason": "http_404", "response_status": 404}),
            "latest_probe_error_message": None,
        },
        {
            "listing_id": 9002,
            "observation_count": 1,
            "total_sightings": 1,
            "first_seen_at": "2026-03-17T10:06:00+00:00",
            "last_seen_at": "2026-03-17T10:06:00+00:00",
            "average_revisit_hours": None,
            "last_observed_run_id": "run-1",
            "canonical_url": "https://www.vinted.fr/items/9002-sold-probable",
            "source_url": "https://www.vinted.fr/items/9002-sold-probable?referrer=catalog",
            "title": "Sold probable robe",
            "brand": "Sandro",
            "size_label": "S",
            "condition_label": "Bon état",
            "price_amount_cents": 3000,
            "price_currency": "€",
            "total_price_amount_cents": 3300,
            "total_price_currency": "€",
            "image_url": "https://images/9002.webp",
            "favourite_count": 2,
            "view_count": 35,
            "user_id": 42,
            "user_login": "bruno",
            "user_profile_url": "https://www.vinted.fr/member/42",
            "created_at_ts": 1711015200,
            "root_title": "Femmes",
            "primary_catalog_id": 2001,
            "primary_root_catalog_id": 1904,
            "primary_catalog_path": "Femmes > Robes",
            "latest_primary_scan_run_id": "run-3",
            "latest_primary_scan_at": "2026-03-19T10:05:00+00:00",
            "follow_up_miss_count": 2,
            "latest_follow_up_miss_at": "2026-03-19T10:05:00+00:00",
            "latest_probe_probed_at": "2026-03-19T11:05:00+00:00",
            "latest_probe_requested_url": "https://www.vinted.fr/items/9002-sold-probable",
            "latest_probe_final_url": "https://www.vinted.fr/items/9002-sold-probable",
            "latest_probe_response_status": 403,
            "latest_probe_outcome": "unknown",
            "latest_probe_detail_json": json.dumps({"reason": "anti_bot_challenge", "response_status": 403, "challenge_markers": ["just a moment"]}),
            "latest_probe_error_message": None,
        },
    ]

    timeline_rows = {
        9001: [
            {
                "run_id": "run-3",
                "listing_id": 9001,
                "observed_at": "2026-03-19T10:05:00+00:00",
                "canonical_url": "https://www.vinted.fr/items/9001-active",
                "source_url": "https://www.vinted.fr/items/9001-active?referrer=catalog",
                "source_catalog_id": 2001,
                "source_page_number": 1,
                "first_card_position": 1,
                "sighting_count": 1,
                "title": "Active robe",
                "brand": "Zara",
                "size_label": "M",
                "condition_label": "Très bon état",
                "price_amount_cents": 1500,
                "price_currency": "€",
                "total_price_amount_cents": 1650,
                "total_price_currency": "€",
                "image_url": "https://images/9001.webp",
                "raw_card_payload_json": json.dumps({"overlay_title": "Active robe"}),
                "catalog_path": "Femmes > Robes",
                "root_title": "Femmes",
            },
            {
                "run_id": "run-2",
                "listing_id": 9001,
                "observed_at": "2026-03-18T10:05:00+00:00",
                "canonical_url": "https://www.vinted.fr/items/9001-active",
                "source_url": "https://www.vinted.fr/items/9001-active?referrer=catalog",
                "source_catalog_id": 2001,
                "source_page_number": 1,
                "first_card_position": 1,
                "sighting_count": 1,
                "title": "Active robe",
                "brand": "Zara",
                "size_label": "M",
                "condition_label": "Très bon état",
                "price_amount_cents": 1400,
                "price_currency": "€",
                "total_price_amount_cents": 1550,
                "total_price_currency": "€",
                "image_url": "https://images/9001.webp",
                "raw_card_payload_json": json.dumps({"overlay_title": "Active robe"}),
                "catalog_path": "Femmes > Robes",
                "root_title": "Femmes",
            },
        ],
        9002: [
            {
                "run_id": "run-1",
                "listing_id": 9002,
                "observed_at": "2026-03-17T10:06:00+00:00",
                "canonical_url": "https://www.vinted.fr/items/9002-sold-probable",
                "source_url": "https://www.vinted.fr/items/9002-sold-probable?referrer=catalog",
                "source_catalog_id": 2001,
                "source_page_number": 1,
                "first_card_position": 2,
                "sighting_count": 1,
                "title": "Sold probable robe",
                "brand": "Sandro",
                "size_label": "S",
                "condition_label": "Bon état",
                "price_amount_cents": 3000,
                "price_currency": "€",
                "total_price_amount_cents": 3300,
                "total_price_currency": "€",
                "image_url": "https://images/9002.webp",
                "raw_card_payload_json": json.dumps({"overlay_title": "Sold probable robe"}),
                "catalog_path": "Femmes > Robes",
                "root_title": "Femmes",
            }
        ],
    }

    peer_price_rows = {
        (2001, "femmes", "zara", "très bon état"): [1000, 1500, 1700, 1900],
        (2001, "femmes", "sandro", "bon état"): [3000],
        (2001, "femmes", "maje", "neuf"): [4200],
    }
    return ScriptedClickHouseClient(
        state_rows=state_rows,
        timeline_rows=timeline_rows,
        peer_price_rows=peer_price_rows,
    )
