"""Які магазини мають ціни — з каталогу Учасниці 2 (`GET /catalog/stores?city=Київ`).

Магазин вважається «з цінами», якщо `offers_count >= PRICED_MIN_OFFERS` (за замовчуванням 50:
Сільпо №2021 має лише 2 товари). `has_pickup` для цього НЕ використовуємо: є магазини з
`has_pickup=false` і сотнями цін.

Її сервіс працює лише локально, тому джерело — URL або збережений JSON (`backend/data/raw/01_*.json`).
Кілька джерел об'єднуються (ETL ще оновлюється, і вивантаження відрізняються): для кожного магазину
береться максимальний `offers_count`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import httpx

from backend.config import DATA_DIR
from backend.geo.ids import normalize_store_id

DEFAULT_CATALOG_FILES = [DATA_DIR / "raw" / "01_stores_kyiv.json", DATA_DIR / "raw" / "02_stores_kyiv_silpo.json"]


def _rows(payload) -> list[dict]:
    """Живий API віддає список; збережені приклади — {"_description": …, "response": [...]}."""
    if isinstance(payload, dict) and "response" in payload:
        payload = payload["response"]
    if not isinstance(payload, list):
        raise ValueError("очікувався список магазинів /catalog/stores")
    return payload


def load_source(src: str | Path, timeout: float = 15.0) -> list[dict]:
    s = str(src)
    if s.startswith(("http://", "https://")):
        r = httpx.get(s, timeout=timeout)
        r.raise_for_status()
        return _rows(r.json())
    return _rows(json.loads(Path(s).read_text(encoding="utf-8")))


def merge_offer_counts(batches: Iterable[list[dict]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rows in batches:
        for x in rows:
            if not x.get("store_id"):
                continue
            sid = normalize_store_id(x["store_id"], x.get("source"))
            counts[sid] = max(counts.get(sid, 0), int(x.get("offers_count") or 0))
    return counts


def load_offer_counts(sources: Iterable[str | Path] | None = None) -> dict[str, int]:
    srcs = list(sources) if sources else [p for p in DEFAULT_CATALOG_FILES if p.exists()]
    return merge_offer_counts(load_source(s) for s in srcs)
