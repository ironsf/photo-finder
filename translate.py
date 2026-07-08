from __future__ import annotations

import cache

_translator = None


def _get_translator():
    global _translator
    if _translator is None:
        from deep_translator import GoogleTranslator

        _translator = GoogleTranslator(source="auto", target="en")
    return _translator


def to_english(text: str) -> str:
    """Переводит название на английский (с кэшем). Возвращает оригинал при ошибке."""
    text = (text or "").strip()
    if not text:
        return text
    cached = cache.get("translate_en", text)
    if cached is not None:
        return cached
    result = _get_translator().translate(text)
    result = (result or text).strip()
    cache.set("translate_en", text, result)
    return result
