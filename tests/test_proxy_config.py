from __future__ import annotations

from pathlib import Path

from vinted_radar.proxies import (
    DEFAULT_PROXY_FILE,
    mask_proxy_url,
    normalize_proxy_entry,
    resolve_proxy_pool,
)


def test_normalize_proxy_entry_accepts_webshare_format() -> None:
    assert normalize_proxy_entry("45.39.4.37:5462:alice:secret") == "http://alice:secret@45.39.4.37:5462"



def test_mask_proxy_url_redacts_credentials() -> None:
    assert mask_proxy_url("http://alice:secret@45.39.4.37:5462") == "http://***@45.39.4.37:5462"



def test_resolve_proxy_pool_autoloads_default_file_and_deduplicates(tmp_path: Path) -> None:
    proxy_file = tmp_path / DEFAULT_PROXY_FILE
    proxy_file.parent.mkdir(parents=True, exist_ok=True)
    proxy_file.write_text(
        "\n".join(
            [
                "45.39.4.37:5462:alice:secret",
                "http://alice:secret@45.39.4.37:5462",
                "216.173.80.190:6447:bob:token",
            ]
        ),
        encoding="utf-8",
    )

    proxies = resolve_proxy_pool(default_file=proxy_file)

    assert proxies == [
        "http://alice:secret@45.39.4.37:5462",
        "http://bob:token@216.173.80.190:6447",
    ]
