"""Які магазини мають підтверджені ціни: є хоча б один рядок OFFERS з in_stock=true.

Ціни, акції й наявність — зона Учасника 2 і прив'язані до (store_id, товар). Поки доступу до БД немає,
джерело — вивантаження OFFERS у CSV (`backend/data/raw/offers_sample.csv`, поля як у таблиці OFFERS +
source). Коли з'явиться БД, достатньо замінити `load_offer_store_ids()` на запит
`SELECT DISTINCT source, store_id FROM offers WHERE in_stock`.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from backend.config import DATA_DIR
from backend.logsafe import parse_bool

OFFERS_CSV = DATA_DIR / "raw" / "offers_sample.csv"


def store_ids_in_stock(rows: Iterable[dict]) -> set[str]:
    """ID у форматі довідника (`zakaz:48246407`, `silpo:<branchId>`) для магазинів з товаром у наявності."""
    return {f"{r['source'].strip().lower()}:{r['store_id'].strip()}"
            for r in rows if parse_bool(r.get("in_stock")) and r.get("source") and r.get("store_id")}


def load_offer_store_ids(path: Path = OFFERS_CSV) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return store_ids_in_stock(csv.DictReader(f))
