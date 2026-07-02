from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPEN_FACTS_DOMAINS = [
    "world.openfoodfacts.org",
    "world.openbeautyfacts.org",
    "world.openproductsfacts.org",
]

USER_AGENT = "photoFinder/0.1 (contact: stakecraft1@gmail.com)"


def _fetch_json(url: str, timeout: float = 10.0) -> dict | None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def lookup_open_facts(barcode: str) -> dict | None:
    for domain in OPEN_FACTS_DOMAINS:
        url = (
            f"https://{domain}/api/v2/product/{barcode}.json"
            "?fields=product_name,image_front_url,status"
        )
        data = _fetch_json(url)
        if not data or data.get("status") != 1:
            continue
        product = data.get("product", {})
        image_url = product.get("image_front_url")
        if image_url:
            return {
                "source": domain,
                "image_url": image_url,
                "name": product.get("product_name", ""),
            }
    return None
