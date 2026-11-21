"""Публічні функції модуля agent: текст запиту → 3 варіанти кошика з цінами каталогу."""

import logging
import re
from collections import defaultdict
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.optimizer import SMALLER_PACK, Candidate, build_baskets, store_options
from app.agent.parser import parse_request
from app.agent.schemas import Basket, BasketIn, BasketOut, Constraints, ParsedRequest, RequestedItem, StoreNearby
from app.catalog import service as catalog
from app.catalog.schemas import StoreOut
from app.config import get_settings
from app.geo import service as geo

CHAIN_NAMES = {
    "silpo": "Сільпо", "novus": "NOVUS", "auchan": "Auchan", "metro": "METRO", "ultramarket": "Ultramarket",
    "ekomarket": "ЕКО маркет", "megamarket": "MegaMarket", "tavriav": "Таврія В",
}  # fmt: skip
log = logging.getLogger(__name__)
ALLOWED_TAGS = {"sugar", "palm_oil", "lactose", "private_label"}  # теги складу каталогу
OUTSIDE_RADIUS_MAX_KM = 30  # далі за це не пропонуємо, навіть якщо в радіусі порожньо
# Товарів на позицію з каталогу: при 10 найдешевший товар конкретного магазину часто не потрапляв у вибірку
SEARCH_LIMIT = 50
ROAD_FACTOR = 1.3  # вулиці не прямі: пряма відстань × 1.3 ≈ відстань по дорозі
SPEED_KMH = {"walk": 5, "car": 25}


async def parse(text: str) -> ParsedRequest:
    parsed, _ = await parse_request(text)
    return parsed


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def _per_chain(stores: list[StoreNearby], per_chain: int) -> list[StoreNearby]:
    """До per_chain найближчих (за часом) магазинів кожної мережі, від найближчого."""
    by_chain: dict[str, list[StoreNearby]] = defaultdict(list)
    for st in sorted(stores, key=lambda x: (x.duration_min, x.distance_km)):
        if len(by_chain[st.chain]) < per_chain:
            by_chain[st.chain].append(st)
    return sorted((st for group in by_chain.values() for st in group), key=lambda x: x.duration_min)


async def stores_from_geo(
    lat: float, lng: float, c: Constraints, per_chain: int
) -> tuple[list[StoreNearby], list[str]]:
    """Магазини з цінами поруч від модуля geo (Учасник 1): маршрути Valhalla, дефолтний радіус команди.

    Якщо в радіусі магазинів з цінами немає, беремо найближчі з цінами поза радіусом і попереджаємо.

    `has_online_prices` у geo — зі статичного знімка (app/geo/data/stores.json), зробленого до того, як ETL
    завантажив більшість філій Сільпо, тож йому не віримо: беремо всі магазини мереж з онлайн-каталогом
    (Zakaz, Сільпо), а чи є там ціни, вирішує пошук у каталозі. OSM-магазини цін не мають ніколи.
    """
    res = await geo.find_nearby(lat, lng, mode=c.travel_mode, radius_km=c.radius_km)
    warnings: list[str] = []
    priced = [
        s for s in res["stores"]
        if s["source"] != "osm"
        and (not c.preferred_chains or s["chain"] in c.preferred_chains)
    ]  # fmt: skip
    chosen = [s for s in priced if s["in_radius"]]
    farther = [s for s in priced if s["distance_km"] <= OUTSIDE_RADIUS_MAX_KM]
    if not chosen and farther:
        chosen = farther
        warnings.append(f"У радіусі {res['radius_km']:g} км немає магазинів з цінами — показуємо найближчі далі")
    elif res["radius_expanded"]:
        warnings.append(f"Поруч порожньо — радіус збільшено до {res['radius_km']:g} км")
    link = "driving" if c.travel_mode == "car" else "walking"
    stores = [
        StoreNearby(
            store_id=s["store_id"],
            alt_store_ids=s.get("alt_store_ids", []),
            chain=s["chain"],
            chain_name=s.get("chain_name"),
            name=s["name"],
            address=s.get("address"),
            lat=s["lat"],
            lng=s["lng"],
            distance_km=s["distance_km"],
            duration_min=s["duration_min"],
            estimated=s.get("estimated", False),
            maps_url=s["maps_urls"][link],
        )
        for s in chosen
    ]
    return _per_chain(stores, per_chain), warnings


def pick_nearby(stores: list[StoreOut], lat: float, lng: float, c: Constraints, per_chain: int) -> list[StoreNearby]:
    """Запасний варіант, якщо модуль geo недоступний: відстань за прямою × 1.3 з координат каталогу."""
    s = get_settings()
    radius = c.radius_km or (s.agent_radius_car_km if c.travel_mode == "car" else s.agent_radius_walk_km)
    mode = "driving" if c.travel_mode == "car" else "walking"
    by_chain: dict[str, list[StoreNearby]] = defaultdict(list)
    for st in stores:
        if st.lat is None or st.lng is None:
            continue
        if c.preferred_chains and st.chain not in c.preferred_chains:
            continue
        km = round(haversine_km(lat, lng, st.lat, st.lng) * ROAD_FACTOR, 2)
        if km > radius:
            continue
        by_chain[st.chain].append(
            StoreNearby(
                store_id=st.store_id,
                chain=st.chain,
                chain_name=CHAIN_NAMES.get(st.chain),
                name=st.name,
                address=st.address,
                lat=st.lat,
                lng=st.lng,
                distance_km=km,
                duration_min=max(1, round(km / SPEED_KMH[c.travel_mode] * 60)),
                estimated=True,
                maps_url=f"https://www.google.com/maps/dir/?api=1&destination={st.lat},{st.lng}&travelmode={mode}",
            )
        )
    return _per_chain([st for group in by_chain.values() for st in group], per_chain)


async def nearby_stores(
    session: AsyncSession, req: BasketIn, c: Constraints, per_chain: int
) -> tuple[list[StoreNearby], list[str]]:
    """Модуль geo, а якщо він впав — власний розрахунок з координат каталогу."""
    try:
        return await stores_from_geo(req.lat, req.lng, c, per_chain)
    except Exception:
        log.exception("geo.find_nearby failed, falling back to straight-line distance")
    all_stores = await catalog.list_stores(session, city=req.city, with_prices=True)
    return pick_nearby(all_stores, req.lat, req.lng, c, per_chain), ["Маршрути недоступні — відстань оцінено за прямою"]


# Слово, яке є в назвах товарів категорії: «гречка» в каталозі — «Крупа гречана», «батон» — «Хліб».
CATEGORY_WORD = {
    "milk": "молоко", "kefir": "кефір", "curd": "сир", "sour_cream": "сметана", "butter": "масло",
    "cheese": "сир", "eggs": "яйця", "flour": "борошно", "sugar": "цукор", "vanilla_sugar": "вані",
    "buckwheat": "греч", "rice": "рис", "pasta": "макарон", "sunflower_oil": "олія", "bread": "хліб",
    "coffee_ground": "кава", "coffee_beans": "кава", "tea": "чай", "bananas": "банан", "apples": "ябл",
}  # fmt: skip


def _stem(text: str) -> str:
    """Каталог шукає підрядок у назві, тож відкидаємо закінчення: «банани» → «бана» (знайде «Банан»)."""
    return " ".join(w if len(w) <= 4 else w[: max(4, len(w) - 2)] for w in text.lower().split())


def search_attempts(item: RequestedItem) -> list[tuple[str, str | None]]:
    """Від точного до загального: (запит, категорія). Перша спроба з результатами виграє."""
    query = f"{item.search_query} {item.brand}" if item.brand else item.search_query
    # З категорією спершу основа слова: «банани» → «бана» знайде і свіже «Банан», і «Банани в сиропі»,
    # а дешевший за кг вибере оптимізатор. Точний запит лишається для бренду й як наступна спроба.
    attempts = [(_stem(query), item.category), (query, item.category)] if item.category else [(query, None)]
    if item.category and not item.brand:  # бренд не відкидаємо: «молоко Галичина» ≠ будь-яке молоко
        attempts.append((CATEGORY_WORD[item.category], item.category))
    attempts.append((_stem(query), None))  # LLM могла помилитися з категорією
    return list(dict.fromkeys(attempts))


def title_starts_with(title: str, query: str) -> bool:
    """Назва товару починається з першого слова запиту (основи): «Банан» ← «бана», «Яйця курячі» ← «яйця».

    Без категорії каталог шукає підрядок будь-де в назві, і «зелень» знаходить «Сир … з зеленою цибулею».
    """
    words = _stem(re.sub(r"[^\w\s'’ʼ-]", " ", query)).split()
    first = title.lower().split()
    return bool(words and first) and first[0].startswith(words[0])


async def _search(session: AsyncSession, item: RequestedItem, store_ids: list[str], exclude: list[str]):
    for query, category in search_attempts(item):
        try:
            found = await catalog.search_prices(
                session, query=query, store_ids=store_ids, category=category, exclude=exclude, limit=SEARCH_LIMIT
            )
        except ValueError:  # у запиті немає слів, придатних для пошуку
            continue
        products = found.products
        if category is None:  # без фільтра категорії приймаємо лише товари, що НАЗИВАЮТЬСЯ так, як просили
            products = [p for p in products if title_starts_with(p.title, query)]
        if products:
            return products
    return []


async def find_candidates(
    session: AsyncSession, items: list[RequestedItem], stores: list[StoreNearby], exclude: list[str]
) -> tuple[dict[str, list[Candidate]], dict[str, str]]:
    """Ціни кожної позиції в магазинах поруч і причини, чому позицію не знайдено.

    В одній будівлі буває кілька store_id (дві філії Сільпо за однією адресою): шукаємо за всіма,
    а ціну приписуємо основному магазину.
    """
    primary = {alt: st.store_id for st in stores for alt in (st.store_id, *st.alt_store_ids)}
    store_ids = list(primary)
    candidates: dict[str, list[Candidate]] = {}
    reasons: dict[str, str] = {}
    for item in items:  # послідовно: одна AsyncSession не виконує запити паралельно
        item_exclude = list(dict.fromkeys([*exclude, *item.exclude]))
        products = await _search(session, item, store_ids, item_exclude)
        if item.gtin:  # товар вибрано з каталогу на екрані 2 — лише він (якщо знайшовся)
            products = [p for p in products if p.gtin == item.gtin] or products
        best: dict[tuple[int, str], Candidate] = {}  # товар × магазин: найдешевша з філій
        for p in products:
            for price in p.prices:
                sid = primary.get(price.store_id)
                if not price.in_stock or sid is None:
                    continue
                key = (p.product_id, sid)
                if key not in best or price.price < best[key].price.price:
                    best[key] = Candidate(item=item.name, product=p, price=price.model_copy(update={"store_id": sid}))
        candidates[item.name] = list(best.values())
        if not candidates[item.name]:
            # Товар є, але не пройшов фільтр складу (або склад невідомий) — це різні речі для UI
            filtered = item_exclude and await _search(session, item, store_ids, [])
            reasons[item.name] = "filtered_by_composition" if filtered else "not_found"
    return candidates, reasons


def explain(baskets: list[Basket], parsed: ParsedRequest) -> str:
    """Коротке пояснення українською з уже порахованих чисел (без LLM: швидко, безкоштовно, без вигаданих цифр)."""
    if not baskets:
        return "Не вдалося зібрати кошик у магазинах поруч. Спробуйте збільшити радіус або змінити запит."
    best = min(baskets, key=lambda b: (len(b.missing), b.total))
    where = " + ".join(s.chain_name or CHAIN_NAMES.get(s.chain, s.chain) for s in best.stores)
    text = f"Найвигідніше: {where} — {best.total:.2f} грн"
    text += f", економія {best.saving:.2f} грн." if best.saving > 0 else "."
    smaller = [line.requested for line in best.lines if line.note and SMALLER_PACK in line.note]
    if smaller:
        text += f" Пачки трохи менші, ніж просили: {', '.join(smaller)} — порівнюйте ціну за кг."
    if best.missing:
        text += f" Не знайшли поруч: {', '.join(m.name for m in best.missing)}."
    budget = parsed.constraints.budget_uah
    if budget is not None and not best.within_budget:
        text += f" Бюджет {budget:g} грн перевищено на {best.total - Decimal(str(budget)):.2f} грн."
    return text


def parsed_from_items(req: BasketIn) -> ParsedRequest:
    """Список з екрана 2 → ParsedRequest. Назви унікальні: за ними агент зводить ціни й missing."""
    items: list[RequestedItem] = []
    seen: dict[str, int] = {}
    for it in req.items or []:
        name = (
            it.label or it.query or (CATEGORY_WORD[it.category] if it.category else "") or it.gtin or "товар"
        ).strip()
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name} ({seen[name]})"
        search = it.query or it.label or (CATEGORY_WORD[it.category] if it.category else "")
        items.append(
            RequestedItem(
                name=name,
                search_query=search,
                category=it.category,
                quantity=it.need,
                unit=it.unit,
                gtin=it.gtin,
                exclude=[t for t in it.exclude if t in ALLOWED_TAGS],
            )
        )
    return ParsedRequest(
        items=items,
        constraints=Constraints(budget_uah=req.budget_uah, travel_mode=req.mode or "walk", radius_km=req.radius_km),
    )


async def build(session: AsyncSession, req: BasketIn) -> BasketOut:
    s = get_settings()
    if req.items:
        parsed, parser = parsed_from_items(req), "items"  # список уже підтверджено на екрані 2 — без LLM
    else:
        parsed, parser = await parse_request(req.text)
    if not parsed.items:
        raise ValueError("no products found in the request")
    c = parsed.constraints
    # Модуль voice уже витягнув спосіб і радіус з голосу — його значення головніші за повторний розбір
    if req.mode:
        c.travel_mode = req.mode
    if req.radius_km:
        c.radius_km = req.radius_km

    stores, warnings = await nearby_stores(session, req, c, s.agent_stores_per_chain)
    if parser == "rules":
        warnings.append("LLM недоступна: запит розібрано спрощено, рецепти не розкладаються на інгредієнти")
    if not stores:
        warnings.append("Немає магазинів з цінами в заданому радіусі")
        return BasketOut(
            parsed=parsed, parser=parser, stores_considered=0, baskets=[],
            explanation=explain([], parsed), warnings=warnings,
        )  # fmt: skip

    candidates, reasons = await find_candidates(session, parsed.items, stores, list(c.exclude))
    baskets = build_baskets(stores, parsed.items, candidates, c, reasons, s.agent_smart_split_min_saving)
    options = store_options(stores, parsed.items, candidates, c, reasons)
    if baskets and not any(b.within_budget for b in baskets):
        warnings.append(f"Жоден кошик не вкладається в бюджет {c.budget_uah:g} грн")
    return BasketOut(
        parsed=parsed,
        parser=parser,
        stores_considered=len(stores),
        baskets=baskets,
        stores=options,
        explanation=explain(baskets, parsed),
        warnings=warnings,
    )
