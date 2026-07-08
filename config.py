from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def find_default_xlsx() -> Path | None:
    candidates = sorted(BASE_DIR.glob("*.xlsx"))
    return candidates[0] if candidates else None


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")

INPUT_XLSX = find_default_xlsx()
BARCODE_COL = "A"
NAME_COL = "B"
HAS_HEADER = False

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

CACHE_DIR = BASE_DIR / "cache"
CANDIDATES_PER_QUERY = 50  # больше кандидатов на товар, чтобы не «заканчивались» после нескольких «нет»
RETAILER_DOMAINS: list[str] = [
    "nichiduta.ro",
    "kidune.ro",
    "emag.ro",
    "bellfyd.ro",
    "giftday.ro",
    "zeluma.ro",
    "flanco.ro",
]

OUTPUT_DIR = BASE_DIR / "images"
MIN_DIMENSION = 650   # нижняя граница «нормального» размера (в этом диапазоне не трогаем)
MAX_DIMENSION = 1050  # выше — уменьшаем до RESIZE_TARGET
RESIZE_TARGET = 700
# Минимальная длинная сторона, чтобы считать картинку «крупной».
# Кандидаты мельче этого уходят в конец списка и НЕ апскейлятся (см. image_proc).
MIN_IMAGE_DIMENSION = 650
JPEG_QUALITY = 90

REPORT_CSV = BASE_DIR / "report.csv"
SPEND_FILE = CACHE_DIR / "spend.json"
BRAVE_COST_PER_CALL = 0.005
SERPAPI_COST_PER_CALL = 0.025
MAX_PAID_SPEND_USD = 20.0

# ─────────────────────────────────────────────────────────────────────────────
# ИСТОЧНИКИ ПОИСКА — порядок и включение.
# Список = приоритет (сверху вниз). Чтобы выключить источник — уберите его из списка
# (или закомментируйте строку). Чтобы поменять приоритет — переставьте строки.
# Доступные значения:
#   "google" — SerpAPI Google Images  (дороже: ~$0.025/запрос, но качественнее)
#   "brave"  — Brave image search      (дешевле: ~$0.005/запрос)
#   "yandex" — Яндекс.Картинки через SerpAPI (~$0.025/запрос)
#   "bing"   — бесплатный скрейпинг через Playwright (НЕСТАБИЛЬНО, требует playwright)
SEARCH_PROVIDERS = [
    "google",
    "brave",
    # "yandex",
    # "bing",
]
SCRAPE_HEADLESS = True  # для "bing": True = браузер скрыт, False = видно окно (для отладки)

# ─────────────────────────────────────────────────────────────────────────────
# ЗАПРОСЫ — что и в каком порядке ищем для каждого товара.
# Список = порядок попыток. Возможные значения:
#   "barcode"       — только штрихкод              (как оператор ищет вручную)
#   "name_barcode"  — «название штрихкод» вместе
#   "name"          — только название (как в файле, напр. на румынском)
#   "name_en"       — название, переведённое на английский (нужен TRANSLATE_TO_ENGLISH=True)
QUERY_ORDER = [
    "barcode",
    "name_barcode",
    "name",
]
# Перевод названия на английский для запроса "name_en" (требует пакет deep-translator).
TRANSLATE_TO_ENGLISH = False

USE_RELEVANCE_SCORING = True
RELEVANCE_MODEL_ID = "google/siglip2-base-patch16-224"
RELEVANCE_TOP_N = 12
AUTO_ACCEPT_THRESHOLD = 0.9
AUTO_ACCEPT_DELAY_SECONDS = 4
