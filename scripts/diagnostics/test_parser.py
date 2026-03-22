import json
from vinted_radar.parsers.api_catalog_page import parse_api_catalog_page
import logging

logging.basicConfig(level=logging.INFO)

payload = {
    "items": [
        {
            "id": 8438109569,
            "title": "Sujetador wave fitness talla S",
            "price": {
                "amount": "30.0",
                "currency_code": "EUR"
            },
            "is_visible": True,
            "brand_title": "Wave Fitness",
            "path": "/items/8438109569-sujetador",
            "url": "https://www.vinted.fr/items/8438109569",
            "photo": {
                "url": "https://images.vinted.net/t/02_bc8_c8M2CuvqHpw8YRy8w9d115Gk/1200x0/1710926727.jpeg?s=0fa4d17300c02ac16719b674824dc5c4646700c0"
            }
        }
    ],
    "pagination": {
        "current_page": 1,
        "total_pages": 1
    }
}

try:
    page = parse_api_catalog_page(payload, source_catalog_id=1439, source_root_catalog_id=1439)
    print(f"Listings found: {len(page.listings)}")
    for l in page.listings:
        print(l)
except Exception as e:
    print(f"Error parsing: {e}")
