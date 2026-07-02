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

USE_SCRAPE_SEARCH = False  # paused: Bing scraping proved flaky in testing, revisit later
SCRAPE_HEADLESS = True

# Яндекс.Картинки через SerpAPI (движок yandex_images, тот же ключ SerpAPI, платно).
# Срабатывает только как последний запасной источник, когда Brave и Google ничего не дали.
USE_YANDEX_FALLBACK = False

USE_RELEVANCE_SCORING = True
RELEVANCE_MODEL_ID = "google/siglip2-base-patch16-224"
RELEVANCE_TOP_N = 12
AUTO_ACCEPT_THRESHOLD = 0.9
AUTO_ACCEPT_DELAY_SECONDS = 4
