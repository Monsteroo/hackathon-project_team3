"""Кроки Match + Optimize: детермінований Python, без LLM і без БД (легко тестувати)."""

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from math import ceil

from app.agent.schemas import Basket, BasketLine, Constraints, MissingItem, RequestedItem, StoreNearby, StoreOption
from app.catalog.schemas import PriceOut, ProductPricesOut

# «Літр молока» = 1 пачка 950 мл: пачки до 15 % меншої ваги рахуємо як одну
SHRINK_TOLERANCE = 0.15
SMALLER_PACK = "Менша пачка"
UNIT_UA = {"g": "г", "ml": "мл", "pcs": "шт"}


@dataclass(frozen=True)
class Candidate:
    """Конкретний товар у конкретному магазині для позиції запиту."""

    item: str
    product: ProductPricesOut
    price: PriceOut


def _comparable(a: str | None, b: str) -> bool:
    """Г і мл порівнюємо як рівні: каталог часто пише молоко в грамах («950г»), а людина каже «літр»."""
    return a == b or {a, b} == {"g", "ml"}


def make_line(item: RequestedItem, c: Candidate) -> BasketLine:
    p = c.product
    same_unit = bool(p.pack_qty) and _comparable(p.pack_unit, item.unit)
    packs = max(1, ceil(item.quantity / p.pack_qty - SHRINK_TOLERANCE)) if same_unit else 1
    notes = []
    if same_unit and item.unit in ("g", "ml") and packs * p.pack_qty < item.quantity:
        have, want = f"{packs * p.pack_qty:g} {UNIT_UA[p.pack_unit]}", f"{item.quantity:g} {UNIT_UA[item.unit]}"
        notes.append(f"{SMALLER_PACK}: {have} замість {want}")
    if c.price.promo_percent:
        notes.append(f"Акція −{c.price.promo_percent}%")
    note = "; ".join(notes) or None
    return BasketLine(
        requested=item.name,
        product_id=p.product_id,
        title=p.title,
        brand=p.brand,
        img_url=p.img_url,
        store_id=c.price.store_id,
        pack_qty=p.pack_qty,
        pack_unit=p.pack_unit,
        packs=packs,
        price=c.price.price,
        old_price=c.price.old_price,
        promo_percent=c.price.promo_percent,
        unit_price=c.price.unit_price,
        unit_price_label=c.price.unit_price_label,
        line_total=(c.price.price * packs).quantize(Decimal("0.01")),
        tags=p.tags,
        note=note,
    )


def _best_lines(
    store_ids: set[str], items: list[RequestedItem], candidates: dict[str, list[Candidate]]
) -> dict[str, BasketLine]:
    """Найдешевший рядок для кожної позиції серед товарів у цих магазинах."""
    best: dict[str, BasketLine] = {}
    for item in items:
        for c in candidates.get(item.name, []):
            if c.price.store_id in store_ids:
                line = make_line(item, c)
                if item.name not in best or line.line_total < best[item.name].line_total:
                    best[item.name] = line
    return best


def build_baskets(
    stores: list[StoreNearby],
    items: list[RequestedItem],
    candidates: dict[str, list[Candidate]],
    constraints: Constraints,
    missing_reasons: dict[str, str],
    smart_split_min_saving: float = 30.0,
) -> list[Basket]:
    """До трьох варіантів: найближчий, найвигідніший в одному магазині, Smart Split на два магазини."""

    def basket(type_: str, stores_: list[StoreNearby], lines: dict[str, BasketLine]) -> Basket:
        total = sum((line.line_total for line in lines.values()), Decimal("0"))
        missing = [
            MissingItem(name=i.name, reason=missing_reasons.get(i.name, "not_found"))
            for i in items
            if i.name not in lines
        ]
        budget = constraints.budget_uah
        return Basket(
            type=type_,
            stores=stores_,
            lines=list(lines.values()),
            total=total,
            saving=Decimal("0"),
            within_budget=budget is None or total <= Decimal(str(budget)),
            missing=missing,
        )

    singles = [
        basket("cheapest", [s], lines) for s in stores if (lines := _best_lines({s.store_id}, items, candidates))
    ]
    if not singles:
        return []

    # Повніший кошик важливіший за дешевший: спершу менше відсутніх позицій, потім ціна
    def rank(b: Basket) -> tuple:
        return (len(b.missing), b.total)

    cheapest = min(singles, key=rank)
    complete = [b for b in singles if len(b.missing) == len(cheapest.missing)]
    nearest = min(complete, key=lambda b: b.stores[0].duration_min).model_copy(update={"type": "nearest"})
    result = [nearest] if nearest.stores[0].store_id == cheapest.stores[0].store_id else [nearest, cheapest]

    best_split = None
    for a, b in combinations([s.stores[0] for s in singles], 2):
        lines = _best_lines({a.store_id, b.store_id}, items, candidates)
        used = {line.store_id for line in lines.values()}
        if len(used) < 2:
            continue  # усе дешевше в одному магазині — це не split
        split = basket("smart_split", [a, b], lines)
        if best_split is None or rank(split) < rank(best_split):
            best_split = split
    if best_split and (
        len(best_split.missing) < len(cheapest.missing)
        or cheapest.total - best_split.total >= Decimal(str(smart_split_min_saving))
    ):
        result.append(best_split)

    worst = max(b.total for b in singles if len(b.missing) == len(cheapest.missing))
    return [b.model_copy(update={"saving": max(Decimal("0"), worst - b.total)}) for b in result]


def store_options(
    stores: list[StoreNearby],
    items: list[RequestedItem],
    candidates: dict[str, list[Candidate]],
    constraints: Constraints,
    missing_reasons: dict[str, str],
) -> list[StoreOption]:
    """Кожен магазин у радіусі з його кошиком. Сортування: повніший кошик, дешевший, ближчий.

    `cheapest` — перший у цьому порядку (найдешевший серед найповніших), `nearest` — найменший час у дорозі.
    """
    budget = Decimal(str(constraints.budget_uah)) if constraints.budget_uah is not None else None
    options = []
    for s in stores:
        lines = _best_lines({s.store_id}, items, candidates)
        if not lines:
            continue
        total = sum((line.line_total for line in lines.values()), Decimal("0"))
        missing = [
            MissingItem(name=i.name, reason=missing_reasons.get(i.name, "not_found"))
            for i in items
            if i.name not in lines
        ]
        options.append(
            StoreOption(
                store=s,
                lines=list(lines.values()),
                total=total,
                found=len(lines),
                missing=missing,
                within_budget=budget is None or total <= budget,
                cheapest=False,
                nearest=False,
            )
        )
    if not options:
        return []
    options.sort(key=lambda o: (len(o.missing), o.total, o.store.duration_min))
    nearest = min(options, key=lambda o: o.store.duration_min)
    return [o.model_copy(update={"cheapest": i == 0, "nearest": o is nearest}) for i, o in enumerate(options)]
