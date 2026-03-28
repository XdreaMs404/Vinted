from __future__ import annotations

from vinted_radar.card_payload import (
    CARD_EVIDENCE_SOURCE_API,
    CARD_EVIDENCE_SOURCE_HTML,
    CARD_EVIDENCE_SCHEMA_VERSION,
    build_api_card_evidence,
    build_html_card_evidence,
    normalize_card_snapshot,
)


def test_build_html_card_evidence_wraps_minimal_visible_fragments() -> None:
    evidence = build_html_card_evidence(
        data_testid="product-item-id-9001",
        overlay_title="Robe noire, marque: Zara, taille: M, état: Très bon état",
        image_alt="Robe noire",
        description_title="Zara",
        description_subtitle="M · Très bon état",
        price_text="12,50 €",
        total_price_text="14,13 €",
    )

    assert evidence == {
        "schema_version": CARD_EVIDENCE_SCHEMA_VERSION,
        "evidence_source": CARD_EVIDENCE_SOURCE_HTML,
        "fragments": {
            "data_testid": "product-item-id-9001",
            "overlay_title": "Robe noire, marque: Zara, taille: M, état: Très bon état",
            "image_alt": "Robe noire",
            "description_title": "Zara",
            "description_subtitle": "M · Très bon état",
            "price_text": "12,50 €",
            "total_price_text": "14,13 €",
        },
    }


def test_build_api_card_evidence_keeps_only_minimal_explainable_fragments() -> None:
    evidence = build_api_card_evidence(
        {
            "id": 9001,
            "title": "Robe noire",
            "brand": {"id": 88, "title": "Zara"},
            "size_title": "M",
            "status_id": 3,
            "price": {
                "amount": "12.50",
                "currency_code": "EUR",
                "formatted": "12,50 €",
            },
            "total_item_price": {
                "amount": "14.13",
                "currency_code": "EUR",
                "formatted": "14,13 €",
            },
            "user": {"id": 42, "login": "alice"},
            "photo": {"url": "https://img.vinted.fr/9001.jpg"},
            "analytics": {"score": 0.98},
        }
    )

    assert evidence == {
        "schema_version": CARD_EVIDENCE_SCHEMA_VERSION,
        "evidence_source": CARD_EVIDENCE_SOURCE_API,
        "fragments": {
            "title": "Robe noire",
            "brand_title": "Zara",
            "size_title": "M",
            "status_id": 3,
            "price": {
                "amount": "12.50",
                "currency_code": "EUR",
            },
            "total_item_price": {
                "amount": "14.13",
                "currency_code": "EUR",
            },
        },
    }
    assert "user" not in evidence["fragments"]
    assert "photo" not in evidence["fragments"]
    assert "analytics" not in evidence["fragments"]


def test_normalize_card_snapshot_rehydrates_html_minimal_contract() -> None:
    snapshot = normalize_card_snapshot(
        raw_card_payload=build_html_card_evidence(
            data_testid="product-item-id-9001",
            overlay_title="Robe noire, marque: Zara, taille: M, état: Très bon état",
            image_alt="Robe noire",
            description_title="Zara",
            description_subtitle="M · Très bon état",
            price_text="12,50 €",
            total_price_text="14,13 €",
        ),
        source_url="https://www.vinted.fr/items/9001-robe-noire?referrer=catalog",
        image_url="https://img.vinted.fr/9001.jpg",
    )

    assert snapshot == {
        "canonical_url": "https://www.vinted.fr/items/9001-robe-noire",
        "source_url": "https://www.vinted.fr/items/9001-robe-noire?referrer=catalog",
        "title": "Robe noire",
        "brand": "Zara",
        "size_label": "M",
        "condition_label": "Très bon état",
        "price_amount_cents": 1250,
        "price_currency": "€",
        "total_price_amount_cents": 1413,
        "total_price_currency": "€",
        "image_url": "https://img.vinted.fr/9001.jpg",
    }


def test_normalize_card_snapshot_rehydrates_api_minimal_contract() -> None:
    snapshot = normalize_card_snapshot(
        raw_card_payload=build_api_card_evidence(
            {
                "title": "Robe noire",
                "brand_title": "Zara",
                "size_title": "M",
                "status_id": 3,
                "price": {"amount": "12.50", "currency_code": "EUR"},
                "total_item_price": {"amount": "14.13", "currency_code": "EUR"},
                "user": {"id": 42, "login": "alice"},
            }
        ),
        source_url="https://www.vinted.fr/items/9001-robe-noire",
        image_url="https://img.vinted.fr/9001.jpg",
    )

    assert snapshot == {
        "canonical_url": "https://www.vinted.fr/items/9001-robe-noire",
        "source_url": "https://www.vinted.fr/items/9001-robe-noire",
        "title": "Robe noire",
        "brand": "Zara",
        "size_label": "M",
        "condition_label": "Très bon état",
        "price_amount_cents": 1250,
        "price_currency": "€",
        "total_price_amount_cents": 1413,
        "total_price_currency": "€",
        "image_url": "https://img.vinted.fr/9001.jpg",
    }


def test_normalize_card_snapshot_keeps_legacy_api_payloads_compatible() -> None:
    snapshot = normalize_card_snapshot(
        raw_card_payload={
            "id": 9001,
            "title": "Robe noire",
            "brand": {"id": 88, "title": "Zara"},
            "size_title": "M",
            "status": "Comme neuf",
            "price": {"amount": "12.50", "currency_code": "EUR", "formatted": "12,50 €"},
            "total_item_price": {"amount": "14.13", "currency_code": "EUR", "formatted": "14,13 €"},
            "user": {"id": 42, "login": "alice"},
        },
        source_url="https://www.vinted.fr/items/9001-robe-noire",
    )

    assert snapshot["title"] == "Robe noire"
    assert snapshot["brand"] == "Zara"
    assert snapshot["size_label"] == "M"
    assert snapshot["condition_label"] == "Comme neuf"
    assert snapshot["price_amount_cents"] == 1250
    assert snapshot["total_price_amount_cents"] == 1413
