from __future__ import annotations

import json
import urllib.parse
import urllib.request

import cache
import config
import state


def brave_image_search(query: str, count: int = None) -> list[dict]:
    cached = cache.get("brave", query)
    if cached is not None:
        return cached

    state.check_spend_limit()
    count = count or config.CANDIDATES_PER_QUERY
    url = "https://api.search.brave.com/res/v1/images/search?" + urllib.parse.urlencode(
        {"q": query, "count": count}
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": config.BRAVE_API_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    state.record_paid_call(config.BRAVE_COST_PER_CALL)

    candidates = []
    for r in data.get("results", []):
        props = r.get("properties", {})
        image_url = props.get("url")
        if not image_url:
            continue
        candidates.append(
            {
                "image_url": image_url,
                "thumbnail_url": r.get("thumbnail", {}).get("src", ""),
                "page_url": r.get("url", ""),
                "domain": r.get("source", ""),
                "width": props.get("width"),
                "height": props.get("height"),
            }
        )

    cache.set("brave", query, candidates)
    return candidates


def serpapi_image_search(query: str) -> list[dict]:
    cached = cache.get("serpapi", query)
    if cached is not None:
        return cached

    state.check_spend_limit()
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(
        {"engine": "google_images", "q": query, "api_key": config.SERPAPI_KEY}
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    state.record_paid_call(config.SERPAPI_COST_PER_CALL)

    candidates = []
    for r in data.get("images_results", []):
        image_url = r.get("original")
        if not image_url:
            continue
        candidates.append(
            {
                "image_url": image_url,
                "thumbnail_url": r.get("thumbnail", ""),
                "page_url": r.get("link", ""),
                "domain": r.get("source", ""),
                "width": r.get("original_width"),
                "height": r.get("original_height"),
            }
        )

    cache.set("serpapi", query, candidates)
    return candidates


def yandex_image_search(query: str) -> list[dict]:
    cached = cache.get("yandex", query)
    if cached is not None:
        return cached

    state.check_spend_limit()
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(
        {"engine": "yandex_images", "text": query, "api_key": config.SERPAPI_KEY}
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    state.record_paid_call(config.SERPAPI_COST_PER_CALL)

    candidates = []
    for r in data.get("images_results", []):
        image_url = r.get("original")
        if not image_url:
            continue
        candidates.append(
            {
                "image_url": image_url,
                "thumbnail_url": r.get("thumbnail", ""),
                "page_url": r.get("link", ""),
                "domain": r.get("source", ""),
                "width": r.get("original_width"),
                "height": r.get("original_height"),
            }
        )

    cache.set("yandex", query, candidates)
    return candidates


def _is_retailer_domain(domain: str) -> bool:
    return any(rd in domain for rd in config.RETAILER_DOMAINS)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=lambda c: not _is_retailer_domain(c.get("domain", "")))


def _finalize(candidates: list[dict], name: str) -> list[dict]:
    candidates = rank_candidates(candidates)
    if config.USE_RELEVANCE_SCORING and name:
        import relevance

        candidates = relevance.rank_by_relevance(candidates, name)
    return candidates


def _query_for_kind(kind: str, code: str, name: str) -> str:
    if kind == "barcode":
        return code
    if kind == "name":
        return name
    if kind == "name_barcode":
        return f"{name} {code}".strip() if (name or code) else ""
    if kind == "name_en":
        if not (name and config.TRANSLATE_TO_ENGLISH):
            return ""
        try:
            import translate

            return translate.to_english(name)
        except Exception as e:
            print(f"[translate] пропущен перевод «{name}»: {e}")
            return ""
    return ""


def _build_queries(code: str, name: str) -> list[str]:
    """Строит список поисковых запросов согласно config.QUERY_ORDER (без дублей и пустых)."""
    queries = []
    for kind in config.QUERY_ORDER:
        q = _query_for_kind(kind, code, name)
        if q and q not in queries:
            queries.append(q)
    return queries


_PROVIDER_FNS = {
    "google": lambda: serpapi_image_search,
    "brave": lambda: brave_image_search,
    "yandex": lambda: yandex_image_search,
}


def _provider_fn(name: str):
    if name == "bing":
        import playwright_search

        return playwright_search.bing_image_search
    factory = _PROVIDER_FNS.get(name)
    return factory() if factory else None


def _split_by_size(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """Делим на «крупные» и «мелкие» по метаданным размера (когда они есть)."""
    large, small = [], []
    for c in candidates:
        w, h = c.get("width"), c.get("height")
        if w and h and max(w, h) < config.MIN_IMAGE_DIMENSION:
            c["too_small"] = True
            small.append(c)
        else:
            large.append(c)
    return large, small


def rank_batch(candidates: list[dict], name: str) -> list[dict]:
    """Ранжируем одну порцию: крупные (домен+SigLIP2) впереди, мелкие — в конец."""
    large, small = _split_by_size(candidates)
    if large:
        return _finalize(large, name) + rank_candidates(small)
    return _finalize(small, name)


def build_search_plan(code: str, name: str) -> list[tuple]:
    """Упорядоченный план (провайдер, запрос) по config.SEARCH_PROVIDERS × config.QUERY_ORDER.

    Порядок в списках задаёт приоритет. Каждый шаг — один платный вызов; UI подгружает
    следующий шаг только когда пользователь исчерпал текущих кандидатов, поэтому обычно
    тратится 1 вызов на товар (первый провайдер × первый запрос).
    """
    queries = _build_queries(code, name)
    plan = []
    for provider_name in config.SEARCH_PROVIDERS:
        fn = _provider_fn(provider_name)
        if fn is None:
            continue
        for q in queries:
            plan.append((fn, q))
    return plan


def search_candidates(code: str, name: str) -> list[dict]:
    """Первая порция кандидатов (для тестов/обратной совместимости)."""
    for fn, query in build_search_plan(code, name):
        candidates = fn(query)
        if candidates:
            return rank_batch(candidates, name)
    return []
