from __future__ import annotations

import hashlib
import json
from pathlib import Path

import config


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode()).hexdigest()
    return config.CACHE_DIR / namespace / f"{digest}.json"


def get(namespace: str, key: str):
    path = _path(namespace, key)
    if path.exists():
        return json.loads(path.read_text())
    return None


def set(namespace: str, key: str, value) -> None:
    path = _path(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
