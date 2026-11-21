"""Довідник магазинів: злиття списку Учасника 2 (Zakaz.ua + Сільпо) з фізичними магазинами з OSM.

Ціни й наявність — зона Учасника 2. Тут лише «де стоїть магазин» і чи є для нього онлайн-ціни.
Збирається скриптом `scripts/build_stores.py` у `backend/data/stores.json`, читається `load_stores()`.
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from typing import Iterable

from backend.config import DATA_DIR
from backend.geo.distance import haversine_km
from backend.logsafe import parse_bool

STORES_JSON = DATA_DIR / "stores.json"

CHAIN_NAMES = {
    "silpo": "Сільпо",
    "novus": "NOVUS",
    "auchan": "Auchan",
    "metro": "METRO",
    "ekomarket": "ЕКО маркет",
    "megamarket": "Megamarket",
    "ultramarket": "Ultramarket",
    "zaraz": "За Раз",
    "epicentr": "Епіцентр FOOD",
    "tavriav": "Таврія В",
    "torba": "Torba",
    "grono": "Grono",
    "ideal": "Ideal",
    "chudomarket": "Чудомаркет",
    "kharkiv": "Харків",
    "vostorg": "Восторг",
    "onde": "Onde",
}

# brand з OSM → наш chain. Невідомі бренди ігноруємо.
OSM_BRAND_TO_CHAIN = {
    "novus": "novus", "новус": "novus",
    "auchan": "auchan", "ашан": "auchan", "my auchan": "auchan", "myauchan": "auchan", "мій ашан": "auchan",
    "metro": "metro", "метро": "metro",
    "еко маркет": "ekomarket", "эко маркет": "ekomarket", "eko market": "ekomarket", "екомаркет": "ekomarket",
    "megamarket": "megamarket", "мегамаркет": "megamarket",
    "ultramarket": "ultramarket", "ультрамаркет": "ultramarket",
    "за раз": "zaraz", "za raz": "zaraz",
}
# Сільпо з OSM не беремо: API Сільпо дає повний список з координатами.
OSM_SKIP_CHAINS = {"silpo"}

MERGE_RADIUS_KM = 0.2      # OSM-точка тієї ж мережі ближче 200 м = той самий магазин
OSM_DEDUP_RADIUS_KM = 0.05  # node + way одного магазину в OSM
UA_PROXIMITY_KM = 25.0      # OSM-точка далі 25 км від будь-якого магазину зі списку — не наша територія
FOREIGN_TLDS = (".ro/", ".pl/", ".md/", ".hu/", ".sk/", ".ru/", ".by/", ".lt/", ".ro", ".pl", ".md", ".hu", ".sk")


def _place_key(lat: float, lng: float) -> str:
    # ~10 м: магазини в одному ТЦ (Megamarket/Ultramarket/За Раз) → одна точка на карті
    return f"{round(lat, 4):.4f},{round(lng, 4):.4f}"


UA_BBOX = (44.0, 22.0, 52.5, 40.3)  # lat_min, lng_min, lat_max, lng_max


def in_ukraine_bbox(lat: float, lng: float) -> bool:
    return UA_BBOX[0] <= lat <= UA_BBOX[2] and UA_BBOX[1] <= lng <= UA_BBOX[3]


def stores_from_csv(rows: Iterable[dict]) -> list[dict]:
    out = []
    for r in rows:
        name = (r.get("name") or "").strip()
        city = (r.get("city") or "").strip()
        if "delete_" in name or not r.get("lat") or not r.get("lng"):
            continue  # службові/видалені філії Сільпо без міста
        if not in_ukraine_bbox(float(r["lat"]), float(r["lng"])):
            continue  # биті координати в джерелі (напр. 1.0,1.0)
        chain = (r.get("chain") or "").strip().lower()
        source = (r.get("source") or "").strip().lower()
        sid = (r.get("store_id") or "").strip()
        out.append({
            "id": f"{source}:{sid}",
            "source": source,
            "source_store_id": sid,
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "name": name,
            "city": city,
            "address": (r.get("address") or "").strip(),
            "lat": float(r["lat"]),
            "lng": float(r["lng"]),
            "has_pickup": parse_bool(r.get("pickup", "")),
            "online_catalog": True,       # магазин є в Zakaz.ua / Сільпо
            "has_online_prices": False,   # true лише якщо в OFFERS є товари in_stock (apply_offers)
            "alt_ids": [],
        })
    return out


SAME_STORE_RADIUS_KM = 0.06  # дві філії однієї мережі ближче 60 м = один фізичний магазин


def dedup_same_address(stores: list[dict]) -> list[dict]:
    """Дві філії однієї мережі за однією адресою (типово Сільпо) → один магазин з alt_ids.

    Та сама адреса або відстань < 60 м (адреси в джерелі пишуть по-різному:
    «пл. Спортивна, 1А» / «пл. Спортивна, пл, 1А»). Основним лишаємо has_pickup=True,
    інші ID — в alt_ids, щоб ціни Учасника 2 знаходились за будь-яким із них.
    """
    groups: list[list[dict]] = []
    for s in sorted(stores, key=lambda s: (not s["has_pickup"], s["id"])):
        for g in groups:
            head = g[0]
            if head["chain"] == s["chain"] and (
                (head["city"].lower(), head["address"].lower()) == (s["city"].lower(), s["address"].lower())
                or haversine_km(head["lat"], head["lng"], s["lat"], s["lng"]) < SAME_STORE_RADIUS_KM
            ):
                g.append(s)
                break
        else:
            groups.append([s])
    out = []
    for group in groups:
        main = dict(group[0])
        main["alt_ids"] = [s["id"] for s in group[1:]]
        out.append(main)
    return out


def _osm_chain(tags: dict) -> str | None:
    for key in ("brand", "name"):
        v = (tags.get(key) or "").strip().lower()
        if v in OSM_BRAND_TO_CHAIN:
            return OSM_BRAND_TO_CHAIN[v]
    return None


def _is_foreign(tags: dict) -> bool:
    country = (tags.get("addr:country") or "").upper()
    if country and country != "UA":
        return True
    site = (tags.get("website") or tags.get("contact:website") or "").lower()
    return any(t in site for t in FOREIGN_TLDS)


def stores_from_osm(elements: Iterable[dict]) -> list[dict]:
    out = []
    for e in elements:
        tags = e.get("tags") or {}
        chain = _osm_chain(tags)
        if not chain or chain in OSM_SKIP_CHAINS or _is_foreign(tags):
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        street = tags.get("addr:street", "")
        house = tags.get("addr:housenumber", "")
        out.append({
            "id": f"osm:{e['type'][0]}{e['id']}",
            "source": "osm",
            "source_store_id": f"{e['type'][0]}{e['id']}",
            "chain": chain,
            "chain_name": CHAIN_NAMES.get(chain, chain),
            "name": tags.get("name") or CHAIN_NAMES.get(chain, chain),
            "city": tags.get("addr:city", ""),
            "address": ", ".join(x for x in (street, house) if x),
            "lat": float(lat),
            "lng": float(lng),
            "has_pickup": False,
            "online_catalog": False,
            "has_online_prices": False,
            "alt_ids": [],
        })
    return out


def apply_offers(stores: list[dict], offer_store_ids: set[str]) -> int:
    """has_online_prices = для магазину (або його alt_ids) є рядки OFFERS з in_stock=true."""
    n = 0
    for s in stores:
        s["has_online_prices"] = s["id"] in offer_store_ids or any(a in offer_store_ids for a in s["alt_ids"])
        n += s["has_online_prices"]
    return n


def merge_osm(listed: list[dict], osm: list[dict]) -> tuple[list[dict], dict]:
    """Додає OSM-магазини, яких немає у списку Учасника 2. Повертає (магазини, статистика)."""
    stats = {"osm_in": len(osm), "osm_far_from_ua": 0, "osm_dup": 0, "osm_matched_listed": 0, "osm_added": 0}
    by_chain: dict[str, list[dict]] = defaultdict(list)
    for s in listed:
        by_chain[s["chain"]].append(s)

    added: list[dict] = []
    for o in osm:
        nearest_any = min((haversine_km(o["lat"], o["lng"], s["lat"], s["lng"]) for s in listed), default=1e9)
        if nearest_any > UA_PROXIMITY_KM:
            stats["osm_far_from_ua"] += 1
            continue
        if any(haversine_km(o["lat"], o["lng"], a["lat"], a["lng"]) < OSM_DEDUP_RADIUS_KM
               for a in added if a["chain"] == o["chain"]):
            stats["osm_dup"] += 1
            continue
        match = next((s for s in by_chain[o["chain"]]
                      if haversine_km(o["lat"], o["lng"], s["lat"], s["lng"]) <= MERGE_RADIUS_KM), None)
        if match:
            stats["osm_matched_listed"] += 1
            continue
        if not o["city"]:
            near = min(listed, key=lambda s: haversine_km(o["lat"], o["lng"], s["lat"], s["lng"]))
            o["city"] = near["city"]
        added.append(o)
    stats["osm_added"] = len(added)
    return listed + added, stats


def assign_places(stores: list[dict]) -> list[dict]:
    for s in stores:
        s["place_id"] = _place_key(s["lat"], s["lng"])
    return stores


def build_directory(csv_rows: Iterable[dict], osm_elements: Iterable[dict],
                    offer_store_ids: set[str] | None = None,
                    cities: Iterable[str] | None = None) -> tuple[list[dict], dict]:
    """cities=None — усі міста; інакше лише магазини цих міст (за полем city)."""
    listed = dedup_same_address(stores_from_csv(csv_rows))
    stores, stats = merge_osm(listed, stores_from_osm(osm_elements))
    stats["listed"] = len(listed)
    if cities is not None:
        keep = {c.lower() for c in cities}
        stats["dropped_other_cities"] = sum(s["city"].lower() not in keep for s in stores)
        stores = [s for s in stores if s["city"].lower() in keep]
    stats["total"] = len(stores)
    stats["with_offers"] = apply_offers(stores, offer_store_ids or set())
    return assign_places(stores), stats


@lru_cache
def load_stores() -> tuple[dict, ...]:
    data = json.loads(STORES_JSON.read_text(encoding="utf-8"))
    return tuple(data["stores"])
