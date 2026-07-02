from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

import config
import image_proc

_model = None
_processor = None


def _load():
    global _model, _processor
    if _model is None:
        _processor = AutoProcessor.from_pretrained(config.RELEVANCE_MODEL_ID)
        _model = AutoModel.from_pretrained(config.RELEVANCE_MODEL_ID).eval()
    return _model, _processor


def score_batch(images: list[Image.Image], text: str) -> list[float]:
    model, processor = _load()
    inputs = processor(
        text=[text.lower()],
        images=[img.convert("RGB") for img in images],
        padding="max_length",
        max_length=64,
        return_tensors="pt",
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits_per_image).squeeze(-1)
    return probs.tolist() if probs.dim() else [probs.item()]


def _safe_download(url: str) -> bytes | None:
    try:
        return image_proc.download_image(url)
    except Exception:
        return None


def rank_by_relevance(candidates: list[dict], text: str, top_n: int = None) -> list[dict]:
    top_n = top_n or config.RELEVANCE_TOP_N
    subset = candidates[:top_n]
    tail = candidates[top_n:]

    urls = [c.get("thumbnail_url") or c["image_url"] for c in subset]
    with ThreadPoolExecutor(max_workers=5) as pool:
        raw_images = list(pool.map(_safe_download, urls))

    images, scored_candidates = [], []
    for raw, candidate in zip(raw_images, subset):
        if raw is None:
            continue
        try:
            images.append(Image.open(BytesIO(raw)))
            scored_candidates.append(candidate)
        except Exception:
            continue

    if not images:
        return candidates

    scores = score_batch(images, text)
    for candidate, s in zip(scored_candidates, scores):
        candidate["relevance"] = s

    unscored = [c for c in subset if c not in scored_candidates]
    ranked = sorted(scored_candidates, key=lambda c: -c["relevance"])
    return ranked + unscored + tail
