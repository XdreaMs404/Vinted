from __future__ import annotations

import codecs
import json
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from vinted_radar.models import CatalogNode

BASE_URL = "https://www.vinted.fr"
_ALLOWED_ROOTS = {"Femmes", "Hommes"}
_CATALOG_TREE_RE = re.compile(r'\\"catalogTree\\":')


class CatalogTreeParseError(RuntimeError):
    pass


def parse_catalog_tree_from_html(html: str, allowed_root_titles: set[str] | None = None) -> list[CatalogNode]:
    allowed_roots = allowed_root_titles or _ALLOWED_ROOTS
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script"):
        text = script.get_text() or ""
        if not text:
            continue
        match = _CATALOG_TREE_RE.search(text)
        if not match:
            continue
        payload = _extract_escaped_json_array(text[match.end() :])
        tree = json.loads(codecs.decode(payload, "unicode_escape"))
        nodes: list[CatalogNode] = []
        for root in tree:
            if root.get("title") not in allowed_roots:
                continue
            nodes.extend(_walk_catalog(root, root_catalog_id=root["id"], root_title=root["title"], parent_catalog_id=None, path=()))
        if nodes:
            return nodes

    raise CatalogTreeParseError("Could not locate an embedded Homme/Femme catalog tree in the public HTML.")


def _extract_escaped_json_array(text: str) -> str:
    start = text.find("[")
    if start == -1:
        raise CatalogTreeParseError("Embedded catalog tree payload did not contain a JSON array start.")

    depth = 0
    for index, character in enumerate(text[start:], start=start):
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise CatalogTreeParseError("Embedded catalog tree payload ended before the JSON array was closed.")


def _walk_catalog(
    node: dict,
    *,
    root_catalog_id: int,
    root_title: str,
    parent_catalog_id: int | None,
    path: tuple[str, ...],
) -> Iterable[CatalogNode]:
    current_path = (*path, node["title"])
    children = node.get("catalogs") or []

    current = CatalogNode(
        catalog_id=int(node["id"]),
        root_catalog_id=root_catalog_id,
        root_title=root_title,
        parent_catalog_id=parent_catalog_id,
        title=node["title"],
        code=node.get("code"),
        url=urljoin(BASE_URL, node["url"]),
        path=current_path,
        depth=len(current_path) - 1,
        is_leaf=not children,
        allow_browsing_subcategories=bool(node.get("allow_browsing_subcategories", True)),
        order_index=node.get("order"),
    )
    yield current

    for child in children:
        yield from _walk_catalog(
            child,
            root_catalog_id=root_catalog_id,
            root_title=root_title,
            parent_catalog_id=current.catalog_id,
            path=current_path,
        )
