"""Збирає backend/data/stores.json з:
  * backend/data/raw/stores.csv   — список Учасника 2 (Zakaz.ua + Сільпо, тимчасово, поки немає доступу до БД)
  * backend/data/raw/osm_ua_raw.json — фізичні магазини наших мереж з OpenStreetMap (Overpass)

Запуск:  .venv/bin/python scripts/build_stores.py [--refresh-osm]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.geo.directory import STORES_JSON, build_directory  # noqa: E402

RAW = ROOT / "backend" / "data" / "raw"
CSV_PATH = RAW / "stores.csv"
OSM_PATH = RAW / "osm_ua_raw.json"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
OVERPASS_QUERY = (
    '[out:json][timeout:180];'
    'nwr["shop"~"^(supermarket|convenience|wholesale|department_store|mall)$"]'
    '["brand"~"NOVUS|Новус|Ашан|Auchan|METRO|Метро|ЕКО|EKO|Мегамаркет|Megamarket|Ultramarket|Ультрамаркет|За Раз|Za Raz",i]'
    '(44.0,22.0,52.5,40.3);out center tags;'
)


def refresh_osm() -> None:
    import httpx

    for attempt in range(4):
        for url in OVERPASS_URLS:
            try:
                r = httpx.post(url, data={"data": OVERPASS_QUERY}, timeout=200,
                               headers={"User-Agent": "voicecart-hackathon/0.1"})
                if r.status_code == 200 and r.json().get("elements"):
                    OSM_PATH.write_text(r.text, encoding="utf-8")
                    print(f"OSM: {len(r.json()['elements'])} елементів з {url}")
                    return
                print(f"OSM {url}: HTTP {r.status_code}")
            except Exception as e:  # noqa: BLE001
                print(f"OSM {url}: {e}")
        time.sleep(20 * (attempt + 1))
    raise SystemExit("Overpass недоступний — спробуйте пізніше")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-osm", action="store_true")
    args = ap.parse_args()
    if args.refresh_osm or not OSM_PATH.exists():
        refresh_osm()

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    osm = json.loads(OSM_PATH.read_text(encoding="utf-8"))["elements"]
    stores, stats = build_directory(rows, osm)

    STORES_JSON.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {"listed": "stores.csv (Учасник 2: Zakaz.ua + Сільпо)", "osm": "OpenStreetMap © contributors, ODbL"},
        "stats": stats,
        "stores": stores,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(stats, ensure_ascii=False))
    print("за джерелом:", dict(Counter(s["source"] for s in stores)))
    print("за мережею:", dict(Counter(s["chain"] for s in stores).most_common()))
    print("міст:", len({s["city"] for s in stores}), "| точок на карті:", len({s["place_id"] for s in stores}))
    print(f"→ {STORES_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
