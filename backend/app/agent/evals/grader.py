"""Детермінована перевірка ParsedRequest проти очікувань із cases.yaml.

Кожна перевірка повертає Check(name, ok, detail). Кейс пройдено, якщо пройдено всі перевірки.
"""

from dataclasses import dataclass

from app.agent.schemas import ParsedRequest, RequestedItem


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def _stem(word: str) -> str:
    """Грубе відкидання закінчень: «яйця» ~ «яйце», «огірки» ~ «огірок»."""
    word = word.lower().replace("’", "'")
    return word[: max(3, len(word) - 2)]


def _matches(item: RequestedItem, variants: list[str]) -> bool:
    haystack = f"{item.name} {item.search_query}".lower().replace("’", "'")
    return any(all(_stem(w) in haystack for w in v.split()) for v in variants)


def grade(parsed: ParsedRequest, expect: dict) -> list[Check]:
    checks: list[Check] = []
    items = parsed.items
    used: set[int] = set()

    # --- Позиції ---
    for exp in expect.get("items", []):
        label = exp["any"][0]
        idx = next((i for i, it in enumerate(items) if i not in used and _matches(it, exp["any"])), None)
        if idx is None:
            checks.append(Check(f"є «{label}»", False, "не знайдено"))
            continue
        used.add(idx)
        it = items[idx]
        checks.append(Check(f"є «{label}»", True))

        if "category" in exp:
            checks.append(Check(f"категорія «{label}»", it.category == exp["category"], f"отримано {it.category!r}"))
        if "qty" in exp:
            lo, hi = exp["qty"]
            ok = it.unit == exp.get("unit", it.unit) and lo <= it.quantity <= hi
            checks.append(
                Check(
                    f"кількість «{label}»",
                    ok,
                    f"{it.quantity:g} {it.unit}, очікувалось {lo:g}–{hi:g} {exp.get('unit', '')}",
                )
            )
        brand = exp.get("brand")
        got = (it.brand or "").lower()
        if brand:
            checks.append(Check(f"бренд «{label}»", brand.lower() in got, f"отримано {it.brand!r}"))
        elif got:
            checks.append(Check(f"без вигаданого бренду «{label}»", False, f"отримано {it.brand!r}"))

    if expect.get("exact_count"):
        extra = [it.name for i, it in enumerate(items) if i not in used]
        checks.append(Check("без зайвих позицій", not extra, f"зайві: {extra}" if extra else ""))

    for word in expect.get("forbid", []):
        bad = [it.name for it in items if _matches(it, [word])]
        checks.append(Check(f"немає «{word}»", not bad, f"знайдено: {bad}" if bad else ""))

    # --- Обмеження (якщо не вказані — перевіряємо значення за замовчуванням) ---
    c = parsed.constraints

    def eq(name: str, got, want) -> None:
        checks.append(Check(name, got == want, f"отримано {got!r}, очікувалось {want!r}"))

    eq("бюджет", c.budget_uah, float(expect["budget_uah"]) if "budget_uah" in expect else None)
    eq("транспорт", c.travel_mode, expect.get("travel_mode", "walk"))
    eq("радіус", c.radius_km, float(expect["radius_km"]) if "radius_km" in expect else None)
    eq("мережі", sorted(c.preferred_chains), sorted(expect.get("preferred_chains", [])))

    eq("виключення", sorted(c.exclude), sorted(expect.get("exclude", [])))

    if "servings" in expect:
        eq("порції", parsed.servings, expect["servings"])

    return checks
