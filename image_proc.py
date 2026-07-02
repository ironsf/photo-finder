from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

import config

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _image_cache_path(url: str) -> Path:
    key = hashlib.sha1(url.encode()).hexdigest()
    return config.CACHE_DIR / "images" / f"{key}.bin"


def _sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    safe_path = quote(parts.path, safe="/%:@&=+$,;")
    safe_query = quote(parts.query, safe="%:@&=+$,;/?")
    return urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))


def download_image(url: str) -> bytes:
    cache_path = _image_cache_path(url)
    if cache_path.exists():
        return cache_path.read_bytes()

    req = Request(_sanitize_url(url), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        data = resp.read()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    return data


def load_image(raw: bytes) -> Image.Image:
    img = Image.open(BytesIO(raw))
    img.load()
    return ImageOps.exif_transpose(img)


def _flatten_to_white(img: Image.Image) -> Image.Image:
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if not has_alpha:
        return img.convert("RGB")
    img = img.convert("RGBA")
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[-1])
    return background


def is_too_small(width: int, height: int) -> bool:
    """Картинка мельче требуемого «крупного» размера (по длинной стороне)."""
    return max(width, height) < config.MIN_IMAGE_DIMENSION


def prepare_image(raw: bytes) -> tuple[Image.Image, dict]:
    img = load_image(raw)
    src_width, src_height = img.size
    img = _flatten_to_white(img)

    largest = max(src_width, src_height)
    too_small = is_too_small(src_width, src_height)

    # Только уменьшаем крупные; мелкие НЕ апскейлим (лучше честный маленький размер, чем мыло).
    resized = largest > config.MAX_DIMENSION
    if resized:
        scale = config.RESIZE_TARGET / largest
        new_size = (round(src_width * scale), round(src_height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    return img, {
        "source_size": (src_width, src_height),
        "final_size": img.size,
        "resized": resized,
        "too_small": too_small,
        "low_res": too_small,  # обратная совместимость со старым полем в отчёте
    }


def save_image(img: Image.Image, code: str) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / f"{code}.jpg"
    img.save(path, "JPEG", quality=config.JPEG_QUALITY)
    return path


def process_candidate(url: str, code: str) -> tuple[Path, dict]:
    raw = download_image(url)
    img, info = prepare_image(raw)
    path = save_image(img, code)
    return path, info
