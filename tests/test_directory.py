from backend.geo.directory import (
    build_directory,
    dedup_same_address,
    load_stores,
    stores_from_csv,
    stores_from_osm,
)
from backend.geo.distance import haversine_km
from backend.geo.offers import load_offer_store_ids, store_ids_in_stock


def row(**kw):
    base = {"source": "zakaz", "chain": "novus", "store_id": "1", "name": "NOVUS A", "city": "Київ",
            "address": "Вулиця, 1", "lat": "50.45", "lng": "30.52", "pickup": "True"}
    base.update(kw)
    return base


def osm(id_, lat, lng, brand="Novus", **tags):
    return {"type": "node", "id": id_, "lat": lat, "lon": lng, "tags": {"brand": brand, "shop": "supermarket", **tags}}


def test_haversine_known_distance():
    # Хрещатик 22 → NOVUS SkyMall: ~5.5 км по прямій
    assert 5.0 < haversine_km(50.4498, 30.5231, 50.4932, 30.5581) < 6.0
    assert haversine_km(50.0, 30.0, 50.0, 30.0) == 0


def test_csv_ids_and_deleted_rows():
    stores = stores_from_csv([
        row(),
        row(source="silpo", chain="silpo", store_id="abc", name="Сільпо №delete_x", city=""),
        row(source="silpo", chain="silpo", store_id="bad", lat="1.0", lng="1.0"),
    ])
    assert [s["id"] for s in stores] == ["zakaz:1"]
    assert stores[0]["online_catalog"] is True
    assert stores[0]["has_online_prices"] is False  # ціни підтверджує лише OFFERS
    assert stores[0]["chain_name"] == "NOVUS"


def test_prices_come_only_from_offers_in_stock():
    rows = [row(store_id="1"), row(store_id="2", lat="50.47", address="Інша, 2"),
            row(source="silpo", chain="silpo", store_id="main", lat="50.49"),
            row(source="silpo", chain="silpo", store_id="old", lat="50.4900", pickup="False")]
    offers = store_ids_in_stock([
        {"source": "zakaz", "store_id": "1", "in_stock": "True"},
        {"source": "zakaz", "store_id": "2", "in_stock": "False"},   # нема в наявності → не рахується
        {"source": "silpo", "store_id": "old", "in_stock": "true"},  # ціни на alt_id → магазин з цінами
    ])
    stores, stats = build_directory(rows, [], offers)
    priced = {s["id"]: s["has_online_prices"] for s in stores}
    assert priced == {"zakaz:1": True, "zakaz:2": False, "silpo:main": True}
    assert stats["with_offers"] == 2


def test_offers_sample_matches_directory():
    ids = load_offer_store_ids()
    assert len(ids) == 5
    known = {i for s in load_stores() for i in [s["id"], *s["alt_ids"]]}
    assert ids <= known
    assert sum(s["has_online_prices"] for s in load_stores()) >= 4  # 5 ID, частина може бути alt_ids


def test_dedup_same_address_prefers_pickup():
    stores = stores_from_csv([
        row(source="silpo", chain="silpo", store_id="a", pickup="False"),
        row(source="silpo", chain="silpo", store_id="b", pickup="True"),
    ])
    out = dedup_same_address(stores)
    assert len(out) == 1
    assert out[0]["id"] == "silpo:b"
    assert out[0]["alt_ids"] == ["silpo:a"]


def test_dedup_close_points_with_different_address_spelling():
    stores = stores_from_csv([
        row(source="silpo", chain="silpo", store_id="a", address="пл. Спортивна, 1А", lat="50.43800"),
        row(source="silpo", chain="silpo", store_id="b", address="пл. Спортивна, пл, 1А", lat="50.43803"),
        row(source="silpo", chain="silpo", store_id="c", address="Інша, 5", lat="50.44000"),  # ~220 м
    ])
    out = dedup_same_address(stores)
    assert sorted(len(s["alt_ids"]) for s in out) == [0, 1]


def test_osm_filters_foreign_unknown_and_silpo():
    els = [
        osm(1, 50.45, 30.52),
        osm(2, 46.77, 23.6, brand="Auchan", **{"addr:country": "RO"}),
        osm(3, 50.45, 30.52, brand="АТБ"),
        osm(4, 50.45, 30.52, brand="Сільпо"),
        osm(5, 50.45, 30.52, brand="Auchan", website="https://www.auchan.ro/x"),
    ]
    assert [s["id"] for s in stores_from_osm(els)] == ["osm:n1"]


def test_merge_matches_dedups_and_drops_far():
    rows = [row()]  # NOVUS у 50.45, 30.52
    els = [
        osm(1, 50.4505, 30.5205),   # ~65 м від NOVUS зі списку → той самий магазин
        osm(2, 50.46, 30.52),       # ~1.1 км → новий фізичний магазин без цін
        osm(3, 50.4602, 30.5201),   # дубль osm:2 (way того ж магазину)
        osm(4, 44.43, 26.10),       # Бухарест → не наша територія
    ]
    stores, stats = build_directory(rows, els)
    ids = [s["id"] for s in stores]
    assert ids == ["zakaz:1", "osm:n2"]
    assert stats["osm_matched_listed"] == 1 and stats["osm_dup"] == 1 and stats["osm_far_from_ua"] == 1
    added = stores[1]
    assert added["has_online_prices"] is False and added["city"] == "Київ"


def test_same_building_shares_place():
    rows = [row(chain="megamarket", store_id="1", name="M", address="Гетьмана, 6"),
            row(chain="ultramarket", store_id="2", name="U", address="Гетьмана, 6")]
    stores, _ = build_directory(rows, [])
    assert stores[0]["place_id"] == stores[1]["place_id"]


def test_generated_directory_is_sane():
    stores = load_stores()
    assert len(stores) > 500
    assert len({s["id"] for s in stores}) == len(stores)
    assert all(44 < s["lat"] < 53 and 22 < s["lng"] < 41 for s in stores)
    assert not any(s["source"] == "osm" and s["chain"] == "silpo" for s in stores)
