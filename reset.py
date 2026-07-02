"""Сброс прогресса photoFinder.

По умолчанию удаляет прогресс проверки — так все товары снова появятся на проверку:
  - report.csv       (статусы done/skipped/notfound)
  - images/*.jpg     (сохранённые картинки)

Кэш поиска (cache/) и счётчик расходов (spend.json) НЕ трогаются — повторный прогон
не будет заново тратить бюджет на уже выполненные запросы.

Запуск:
  python reset.py          # сбросить прогресс (спросит подтверждение)
  python reset.py --yes    # без подтверждения
  python reset.py --all    # + очистить кэш поиска и счётчик расходов (следующий прогон платный заново)
"""

from __future__ import annotations

import shutil
import sys

import config


def main():
    args = set(sys.argv[1:])
    wipe_all = "--all" in args
    auto_yes = "--yes" in args or "-y" in args

    images = sorted(config.OUTPUT_DIR.glob("*.jpg")) if config.OUTPUT_DIR.exists() else []
    print(f"Будет удалено: report.csv ({'есть' if config.REPORT_CSV.exists() else 'нет'}), "
          f"{len(images)} картинок в images/")
    if wipe_all:
        print("  + очистка cache/ (поиск и spend.json) — следующий прогон будет платным заново")

    if not auto_yes:
        answer = input("Продолжить? [y/N] ").strip().lower()
        if answer not in ("y", "yes", "д", "да"):
            print("Отменено.")
            return

    config.REPORT_CSV.unlink(missing_ok=True)
    for img in images:
        img.unlink()

    if wipe_all and config.CACHE_DIR.exists():
        shutil.rmtree(config.CACHE_DIR)

    print("Готово. Прогресс сброшен.")


if __name__ == "__main__":
    main()
