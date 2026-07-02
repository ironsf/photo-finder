from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import config

FIELDNAMES = [
    "code",
    "name",
    "status",
    "image_url",
    "domain",
    "relevance",
    "auto_accepted",
    "width",
    "height",
    "low_res",
    "error_msg",
    "timestamp",
]
RESUMABLE_STATUSES = {"done", "skipped"}


class QuotaExceededError(Exception):
    pass


def load_report() -> dict[str, dict]:
    if not config.REPORT_CSV.exists():
        return {}
    with config.REPORT_CSV.open(newline="", encoding="utf-8") as f:
        return {row["code"]: row for row in csv.DictReader(f)}


def is_resolved(code: str, report: dict[str, dict]) -> bool:
    row = report.get(code)
    return bool(row and row["status"] in RESUMABLE_STATUSES)


def append_row(row: dict) -> None:
    is_new = not config.REPORT_CSV.exists()
    with config.REPORT_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def make_row(
    code: str,
    name: str,
    status: str,
    candidate: dict = None,
    info: dict = None,
    error_msg: str = "",
    auto_accepted: bool = False,
) -> dict:
    candidate = candidate or {}
    final_size = (info or {}).get("final_size", ("", ""))
    return {
        "code": code,
        "name": name,
        "status": status,
        "image_url": candidate.get("image_url", ""),
        "domain": candidate.get("domain", ""),
        "relevance": candidate.get("relevance", ""),
        "auto_accepted": auto_accepted,
        "width": final_size[0],
        "height": final_size[1],
        "low_res": (info or {}).get("low_res", ""),
        "error_msg": error_msg,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _load_spend() -> float:
    if not config.SPEND_FILE.exists():
        return 0.0
    return json.loads(config.SPEND_FILE.read_text()).get("total_usd", 0.0)


def _save_spend(total: float) -> None:
    config.SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SPEND_FILE.write_text(json.dumps({"total_usd": total}))


def record_paid_call(cost: float) -> float:
    total = _load_spend() + cost
    _save_spend(total)
    return total


def check_spend_limit() -> None:
    if _load_spend() >= config.MAX_PAID_SPEND_USD:
        raise QuotaExceededError(
            f"Достигнут лимит платного бюджета (${config.MAX_PAID_SPEND_USD:.2f}). "
            f"Увеличьте config.MAX_PAID_SPEND_USD, чтобы продолжить."
        )
