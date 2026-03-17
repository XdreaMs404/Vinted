from __future__ import annotations

from vinted_radar.parsers.catalog_page import parse_catalog_page


MINIMAL_CARD_HTML = """
<html>
  <body>
    <div class="new-item-box__container" data-testid="product-item-id-9999">
      <a class="new-item-box__overlay" href="/items/9999-silk-dress?referrer=catalog" title="Silk dress, marque: Maje, État: Neuf, taille: S"></a>
      <img src="https://images/9999.webp" alt="Silk dress, marque: Maje, État: Neuf, taille: S" />
      <div data-testid="product-item-id-9999--price-text">19,50 €</div>
      <div data-testid="total-combined-price">21,45 €</div>
    </div>
  </body>
</html>
"""


def test_catalog_page_normalization_keeps_catalog_context_and_canonical_url() -> None:
    page = parse_catalog_page(MINIMAL_CARD_HTML, source_catalog_id=2001, source_root_catalog_id=1904)

    assert len(page.listings) == 1
    listing = page.listings[0]
    assert listing.listing_id == 9999
    assert listing.source_catalog_id == 2001
    assert listing.source_root_catalog_id == 1904
    assert listing.canonical_url == "https://www.vinted.fr/items/9999-silk-dress"
    assert listing.brand == "Maje"
    assert listing.size_label == "S"
    assert listing.condition_label == "Neuf"
    assert listing.price_amount_cents == 1950
    assert listing.total_price_amount_cents == 2145
