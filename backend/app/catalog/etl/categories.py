"""Канонічні категорії демо.

Кожна категорія складається з пошукового запиту до API магазину і правил для назви товару. Пошук повертає
багато схожого (сир з курагою, ароматизована кава, кокосове молоко), а порівнювати треба однакове з однаковим.
Ключі категорій — це контракт з агентом (див. CLAUDE.md), тому змінюй їх лише після домовленості з командою.
"""

import re
from dataclasses import dataclass

_QUOTES = re.compile(r"[«»\"“”„]")


def normalize_title(title: str) -> str:
    return _QUOTES.sub("", title or "").strip()


@dataclass(frozen=True)
class Category:
    key: str
    query: str
    include: re.Pattern[str]
    exclude: re.Pattern[str] | None = None

    def matches(self, title: str) -> bool:
        text = normalize_title(title)
        if not self.include.search(text):
            return False
        return not (self.exclude and self.exclude.search(text))


def _cat(key: str, query: str, include: str, exclude: str | None = None) -> Category:
    return Category(
        key=key,
        query=query,
        include=re.compile(include, re.IGNORECASE),
        exclude=re.compile(exclude, re.IGNORECASE) if exclude else None,
    )


_FLAVORS = r"шоколад|какао|ваніл|полуниц|банан|карамел|горіх"

CATEGORIES: tuple[Category, ...] = (
    _cat(
        "milk",
        "молоко",
        r"^Молоко\b",
        r"кокос|мигдал|вівсян|рисов|соєв|горіхов|згущ|сух[еа]\b|дитяч|для дітей|" + _FLAVORS,
    ),
    _cat("kefir", "кефір", r"^Кефір\b", _FLAVORS),
    _cat("curd", "сир кисломолочний", r"^Сир кисломолочний\b", r"\s(з|зі|із)\s|ванільн|солодк|для дітей|дитяч"),
    _cat("sour_cream", "сметана", r"^Сметана\s", r"продукт"),
    _cat("butter", "масло вершкове", r"^Масло\b.*вершков", r"шоколад|спред|суміш|наповнювач|часник|зелен"),
    _cat(
        "cheese",
        "сир твердий",
        r"^Сир\b",
        r"кисломолоч|плавлен|сирок|сирний продукт|десерт|глазур|творож|ковбас|паличк|снек",
    ),
    _cat("eggs", "яйця курячі", r"^Яйця курячі\b", r"перепел|\b[СC][23]\b"),
    _cat("flour", "борошно пшеничне", r"^Борошно\b.*пшеничн", r"цільнозерн|грубого|органіч|суміш|для піц|спельт"),
    _cat("sugar", "цукор білий", r"^Цукор\b", r"ваніл|пудр|тростин|кокос|кленов|фруктоз|стеві|замінник"),
    _cat("vanilla_sugar", "ванільний цукор", r"^(Цукор ванільн|Ванільний цукор|Ванілін)"),
    _cat("buckwheat", "крупа гречана", r"^(Крупа гречан|Гречка|Гречана крупа)", r"пластівц|борошно|зелен|локшин|каша"),
    _cat("rice", "рис", r"^Рис\b", r"пластівц|борошно|локшин|папір|оцет|хлібц|дикий|молоко|вафл|каша"),
    _cat("pasta", "макарони", r"^(Макарони|Макаронні вироби|Спагеті)\b", r"соус|готов|швидкого|з сиром"),
    _cat("sunflower_oil", "олія соняшникова", r"^Олія\b.*соняшник", r"спрей|суміш"),
    _cat("bread", "хліб", r"^Хліб\b", r"хлібц|сухар|паличк|чіпс|квас"),
    _cat(
        "coffee_ground",
        "кава мелена",
        r"^Кава мелена\b",
        r"дрип|дріп|фільтр-пакет|капсул|пакетик|без кофеїну|ароматиз|марципан|ірланд|irlandese|amaretto|" + _FLAVORS,
    ),
    _cat("coffee_beans", "кава в зернах", r"^Кава (в зернах|зернова)\b", r"без кофеїну|ароматиз|" + _FLAVORS),
    _cat("tea", "чай чорний", r"^Чай чорний\b", r"холодн|напій|\bice\b"),
    _cat("bananas", "банан", r"^Банан(и)?\b", r"сушен|чипс|чіпс|пюре|йогурт|сік|десерт|морозив|бебі"),
    _cat("apples", "яблука", r"^Яблук[оа]\b", r"сушен|чипс|чіпс|пюре|сік|оцет|джем|пастил|пиріг"),
)

BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}


def select(keys: list[str] | None) -> list[Category]:
    """Категорії за ключами (None = усі). Невідомий ключ — помилка, щоб не мовчати про одруківку."""
    if not keys:
        return list(CATEGORIES)
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise ValueError(f"unknown categories: {', '.join(unknown)}")
    return [BY_KEY[k] for k in keys]
