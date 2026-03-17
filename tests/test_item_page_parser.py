from __future__ import annotations

from vinted_radar.parsers.item_page import parse_item_page_probe


ACTIVE_HTML = '<script>{"type":"buy","section":"sidebar","data":{"item_id":9001,"seller_id":1,"can_buy":true,"instant_buy":true,"is_closed":false,"is_hidden":false,"is_reserved":false}}</script>'
SOLD_HTML = '<script>{"type":"buy","section":"sidebar","data":{"item_id":9002,"seller_id":1,"can_buy":false,"instant_buy":false,"is_closed":true,"is_hidden":false,"is_reserved":false}}</script>'
UNAVAILABLE_HTML = '<script>{"type":"buy","section":"sidebar","data":{"item_id":9003,"seller_id":1,"can_buy":false,"instant_buy":false,"is_closed":false,"is_hidden":true,"is_reserved":false}}</script>'
UNKNOWN_HTML = '<html><body><h1>No buy block here</h1></body></html>'


def test_parse_item_page_probe_detects_active_signal() -> None:
    result = parse_item_page_probe(listing_id=9001, response_status=200, html=ACTIVE_HTML)

    assert result.probe_outcome == "active"
    assert result.detail["can_buy"] is True
    assert result.detail["is_closed"] is False


def test_parse_item_page_probe_detects_sold_signal() -> None:
    result = parse_item_page_probe(listing_id=9002, response_status=200, html=SOLD_HTML)

    assert result.probe_outcome == "sold"
    assert result.detail["is_closed"] is True


def test_parse_item_page_probe_detects_unavailable_signal() -> None:
    result = parse_item_page_probe(listing_id=9003, response_status=200, html=UNAVAILABLE_HTML)

    assert result.probe_outcome == "unavailable"
    assert result.detail["is_hidden"] is True


def test_parse_item_page_probe_treats_404_as_deleted() -> None:
    result = parse_item_page_probe(listing_id=9004, response_status=404, html="")

    assert result.probe_outcome == "deleted"
    assert result.detail["reason"] == "http_404"


def test_parse_item_page_probe_degrades_unknown_shape_to_unknown() -> None:
    result = parse_item_page_probe(listing_id=9005, response_status=200, html=UNKNOWN_HTML)

    assert result.probe_outcome == "unknown"
    assert result.detail["reason"] == "buy_signal_not_found"
