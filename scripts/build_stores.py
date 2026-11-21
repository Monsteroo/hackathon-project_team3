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

from backend.config import priced_min_offers, service_cities  # noqa: E402
from backend.geo.catalog import load_offer_counts  # noqa: E402
from backend.geo.directory import STORES_JSON, build_directory  # noqa: E402
from backend.geo.offers import load_offer_store_ids  # noqa: E402

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


ADDR_CACHE = RAW / "osm_addresses.json"


def fill_addresses(stores: list[dict], fetch: bool) -> int:
    """Магазини з OSM без addr:* → адреса зворотним геокодингом (Nominatim, 1 rps, кеш у файлі)."""
    cache = json.loads(ADDR_CACHE.read_text(encoding="utf-8")) if ADDR_CACHE.exists() else {}
    missing = [s for s in stores if s["source"] == "osm" and not s["address"]]
    if fetch:
        from backend.geo.geocode import reverse

        todo = [s for s in missing if s["id"] not in cache]
        for i, s in enumerate(todo, 1):
            try:
                res = reverse(s["lat"], s["lng"])
                cache[s["id"]] = {"address": res["label"] if res else "", "city": ""}
                if res:  # місто з label прибираємо — воно окремим полем
                    parts = res["label"].split(", ")
                    if len(parts) > 1:
                        cache[s["id"]] = {"address": ", ".join(parts[:-1]), "city": parts[-1]}
            except Exception as e:  # noqa: BLE001
                print(f"  {s['id']}: {e}")
            if i % 20 == 0:
                print(f"  адреси: {i}/{len(todo)}")
                ADDR_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        ADDR_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    filled = 0
    for s in missing:
        hit = cache.get(s["id"])
        if hit and hit["address"]:
            s["address"] = hit["address"]
            s["city"] = s["city"] or hit["city"]
            filled += 1
    return filled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-osm", action="store_true")
    ap.add_argument("--fetch-addresses", action="store_true",
                    help="дозаповнити адреси OSM-магазинів через Nominatim (~1 с на магазин)")
    ap.add_argument("--all-cities", action="store_true",
                    help="усі міста з даних (за замовчуванням — SERVICE_CITIES, зараз Київ)")
    ap.add_argument("--catalog", action="append", default=[],
                    help="URL або JSON /catalog/stores Учасниці 2 (можна кілька — об'єднуються). "
                         "За замовчуванням backend/data/raw/01_stores_kyiv.json і 02_stores_kyiv_silpo.json. "
                         "Напр.: --catalog 'http://localhost:8000/catalog/stores?city=Київ'")
    ap.add_argument("--offers-csv", type=Path,
                    help="запасне джерело: вивантаження OFFERS (CSV), ціни там, де є in_stock=true")
    args = ap.parse_args()
    if args.refresh_osm or not OSM_PATH.exists():
        refresh_osm()

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    osm = json.loads(OSM_PATH.read_text(encoding="utf-8"))["elements"]
    cities = None if args.all_cities else service_cities()
    if args.offers_csv:
        offer_ids, counts = load_offer_store_ids(args.offers_csv), None
        priced_source = args.offers_csv.name
    else:
        counts = load_offer_counts(args.catalog or None)
        offer_ids = {i for i, n in counts.items() if n >= priced_min_offers()}
        priced_source = ", ".join(str(c) for c in args.catalog) if args.catalog else "raw/01_*.json + raw/02_*.json"
    stores, stats = build_directory(rows, osm, offer_ids, cities, counts, priced_min_offers())
    stats["cities"] = cities or "all"
    stats["priced_rule"] = f"offers_count >= {priced_min_offers()}" if counts is not None else "OFFERS in_stock"
    missing = (set(counts) if counts is not None else offer_ids) - {i for s in stores for i in [s["id"], *s["alt_ids"]]}
    if missing:
        print("⚠️ магазини з цінами, яких немає в довіднику:", sorted(missing))
    stats["osm_address_filled"] = fill_addresses(stores, fetch=args.fetch_addresses)

    STORES_JSON.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {"listed": "stores.csv (Учасник 2: Zakaz.ua + Сільпо)", "osm": "OpenStreetMap © contributors, ODbL",
                    "prices": priced_source},
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
