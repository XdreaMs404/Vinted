from __future__ import annotations

from dataclasses import dataclass
import re

_BUY_SIGNAL_RE = re.compile(
    r'"item_id":(?P<item_id>\d+).*?"can_buy":(?P<can_buy>true|false).*?"is_closed":(?P<is_closed>true|false).*?"is_hidden":(?P<is_hidden>true|false).*?"is_reserved":(?P<is_reserved>true|false)',
    re.DOTALL,
)

_CHALLENGE_MARKERS: tuple[str, ...] = (
    "just a moment",
    "attention required",
    "turnstile",
    "cf-chl",
    "challenge-platform",
    "verify you are human",
    "captcha",
    "cloudflare",
)


@dataclass(frozen=True, slots=True)
class ItemPageProbeResult:
    probe_outcome: str
    detail: dict[str, object]


def parse_item_page_probe(*, listing_id: int, response_status: int | None, html: str) -> ItemPageProbeResult:
    challenge_markers = _challenge_markers(html)
    challenge_detected = bool(challenge_markers)

    if response_status in {404, 410}:
        return ItemPageProbeResult(
            probe_outcome="deleted",
            detail={"reason": f"http_{response_status}", "response_status": response_status},
        )

    if response_status is None:
        detail = {"reason": "no_response_status"}
        if challenge_detected:
            detail["challenge_markers"] = challenge_markers
        return ItemPageProbeResult(probe_outcome="unknown", detail=detail)

    if response_status >= 500:
        return ItemPageProbeResult(
            probe_outcome="unknown",
            detail={"reason": f"http_{response_status}", "response_status": response_status},
        )

    if response_status >= 400:
        if challenge_detected or response_status in {403, 429}:
            return ItemPageProbeResult(
                probe_outcome="unknown",
                detail={
                    "reason": "anti_bot_challenge",
                    "response_status": response_status,
                    "challenge_markers": challenge_markers,
                },
            )
        return ItemPageProbeResult(
            probe_outcome="unknown",
            detail={"reason": f"unexpected_http_{response_status}", "response_status": response_status},
        )

    search_text = html.replace('\\"', '"')
    match = _BUY_SIGNAL_RE.search(search_text)
    if match is None:
        if challenge_detected:
            return ItemPageProbeResult(
                probe_outcome="unknown",
                detail={
                    "reason": "anti_bot_challenge",
                    "response_status": response_status,
                    "challenge_markers": challenge_markers,
                },
            )
        return ItemPageProbeResult(
            probe_outcome="unknown",
            detail={"reason": "buy_signal_not_found", "response_status": response_status},
        )

    item_id = int(match.group("item_id"))
    can_buy = _to_bool(match.group("can_buy"))
    is_closed = _to_bool(match.group("is_closed"))
    is_hidden = _to_bool(match.group("is_hidden"))
    is_reserved = _to_bool(match.group("is_reserved"))
    detail = {
        "response_status": response_status,
        "parsed_item_id": item_id,
        "can_buy": can_buy,
        "is_closed": is_closed,
        "is_hidden": is_hidden,
        "is_reserved": is_reserved,
    }

    if item_id != listing_id:
        detail["reason"] = "item_id_mismatch"
        return ItemPageProbeResult(probe_outcome="unknown", detail=detail)
    if can_buy and not is_closed and not is_hidden:
        detail["reason"] = "buy_signal_open"
        return ItemPageProbeResult(probe_outcome="active", detail=detail)
    if is_closed and not can_buy:
        detail["reason"] = "buy_signal_closed"
        return ItemPageProbeResult(probe_outcome="sold", detail=detail)
    if is_hidden or is_reserved or not can_buy:
        detail["reason"] = "buy_signal_unavailable"
        return ItemPageProbeResult(probe_outcome="unavailable", detail=detail)

    detail["reason"] = "buy_signal_ambiguous"
    return ItemPageProbeResult(probe_outcome="unknown", detail=detail)


def _challenge_markers(html: str) -> list[str]:
    lowered = html.casefold()
    return [marker for marker in _CHALLENGE_MARKERS if marker in lowered]


def _to_bool(value: str) -> bool:
    return value == "true"
