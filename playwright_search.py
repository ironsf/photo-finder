from __future__ import annotations

import json
import re
from urllib.parse import urlencode, urlparse

from playwright.sync_api import sync_playwright

import cache
import config

BING_URL = "https://www.bing.com/images/search"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_playwright = None
_browser = None
_context = None


def _get_context():
    global _playwright, _browser, _context
    if _context is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=config.SCRAPE_HEADLESS)
        _context = _browser.new_context(user_agent=USER_AGENT, locale="en-US")
    return _context


def shutdown():
    global _playwright, _browser, _context
    if _browser is not None:
        _browser.close()
    if _playwright is not None:
        _playwright.stop()
    _browser = None
    _context = None
    _playwright = None


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc


def _parse_results(html: str) -> list[dict]:
    candidates = []
    seen_urls = set()
    for match in re.finditer(r'class="iusc"[^>]*\sm="([^"]+)"', html):
        raw = match.group(1).replace("&quot;", '"').replace("&amp;", "&")
        try:
            meta = json.loads(raw)
        except json.JSONDecodeError:
            continue
        image_url = meta.get("murl")
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        page_url = meta.get("purl", "")
        candidates.append(
            {
                "image_url": image_url,
                "thumbnail_url": meta.get("turl", ""),
                "page_url": page_url,
                "domain": _domain_from_url(page_url),
                "width": meta.get("mw"),
                "height": meta.get("mh"),
            }
        )
    return candidates


def bing_image_search(query: str) -> list[dict]:
    cached = cache.get("bing", query)
    if cached is not None:
        return cached

    context = _get_context()
    page = context.new_page()
    html = ""
    query_string = urlencode({"q": query, "form": "HDRSC2"})
    try:
        page.goto(f"{BING_URL}?{query_string}", timeout=20000)
        page.wait_for_selector("a.iusc", timeout=10000)
        page.wait_for_timeout(2000)
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1500)
        html = page.content()
    except Exception:
        html = page.content() if not page.is_closed() else ""
    finally:
        page.close()

    candidates = _parse_results(html)
    cache.set("bing", query, candidates)
    return candidates
