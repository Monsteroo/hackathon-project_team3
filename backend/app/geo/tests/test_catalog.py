import json

import httpx
import pytest

from app.geo import catalog
from app.geo.directory import build_directory, load_stores
from app.geo.ids import normalize_store_id


def row(**kw):
    base = {
        "source": "zakaz",
        "chain": "novus",
        "store_id": "1",
        "name": "N",
        "city": "Київ",
        "address": "Вулиця, 1",
        "lat": "50.45",
        "lng": "30.52",
        "pickup": "True",
    }
    base.update(kw)
    return base


def test_rows_accept_saved_wrapper_and_live_list(tmp_path):
    items = [{"store_id": "48201031", "source": "zakaz", "offers_count": 10}]
    (tmp_path / "w.json").write_text(json.dumps({"_description": "x", "response": items}), encoding="utf-8")
    (tmp_path / "l.json").write_text(json.dumps(items), encoding="utf-8")
    assert catalog.load_source(tmp_path / "w.json") == catalog.load_source(tmp_path / "l.json") == items
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        catalog.load_source(tmp_path / "bad.json")


def test_load_source_from_url(monkeypatch):
    seen = {}

    def fake_get(url, timeout):
        seen["url"] = url
        return httpx.Response(
            200, json=[{"store_id": "1", "source": "zakaz", "offers_count": 60}], request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(catalog.httpx, "get", fake_get)
    rows = catalog.load_source("http://localhost:8000/catalog/stores?city=Київ")
    assert rows[0]["offers_count"] == 60 and seen["url"].endswith("city=Київ")


def test_merge_takes_max_not_overwrite():
    a = [{"store_id": "1", "source": "zakaz", "offers_count": 100}]
    b = [
        {"store_id": "1", "source": "zakaz", "offers_count": 80},
        {"store_id": "1EDB6B34-6894-674E-9198-BF2CAC88BD3A", "source": "silpo", "offers_count": 355},
    ]
    counts = catalog.merge_offer_counts([a, b])
    assert counts == {"zakaz:1": 100, "silpo:1edb6b34-6894-674e-9198-bf2cac88bd3a": 355}


def test_threshold_and_pickup_ignored_and_alt_ids():
    rows = [
        row(store_id="1"),
        row(store_id="2", address="Інша, 2", lat="50.47", pickup="False"),
        row(source="silpo", chain="silpo", store_id="main", lat="50.49", address="Б, 22"),
        row(source="silpo", chain="silpo", store_id="alt", lat="50.49", address="Б, 22", pickup="False"),
    ]
    counts = {"zakaz:1": 2, "zakaz:2": 617, "silpo:alt": 582}
    stores, stats = build_directory(rows, [], None, None, counts, min_offers=50)
    by = {s["id"]: (s["offers_count"], s["has_online_prices"]) for s in stores}
    assert by == {
        "zakaz:1": (2, False),  # як Сільпо №2021: 2 товари — не «з цінами»
        "zakaz:2": (617, True),  # has_pickup=false, але сотні цін — «з цінами»
        "silpo:main": (582, True),
    }  # ціни прийшли на alt_id (№3319 → №2025)
    assert stats["with_offers"] == 2


def test_generated_directory_uses_catalog():
    stores = load_stores()
    priced = [s for s in stores if s["has_online_prices"]]
    assert len(priced) >= 60 and all(s["offers_count"] >= 50 for s in priced)
    names = {s["name"]: s for s in stores}
    assert names["Сільпо №2021"]["has_online_prices"] is False  # лише 2 товари
    assert names["Сільпо №2034"]["has_online_prices"] is True  # є лише у 02 — об'єднання, не перезапис
    assert names["Сільпо №2025"]["offers_count"] == 582  # через alt_id №3319


@pytest.mark.parametrize(
    "raw,source,norm",
    [
        ("48201031", "zakaz", "zakaz:48201031"),
        ("1EDB6B12-C559-61CC-B8C3-EB10F39E9FE0", "silpo", "silpo:1edb6b12-c559-61cc-b8c3-eb10f39e9fe0"),
        ("48201031", None, "zakaz:48201031"),
    ],
)
def test_normalize_with_source(raw, source, norm):
    assert normalize_store_id(raw, source) == norm
