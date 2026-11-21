"""Чисті функції нормалізації: без мережі й БД. Їх легко тестувати, і на них спираються evals."""

import html
import re
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: object) -> Decimal:
    """Гривні з двома знаками. Через str(), щоб float 74.99 не став 74.98999…"""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def kopecks(value: int) -> Decimal:
    """Ціни Zakaz.ua приходять у копійках: 7499 -> 74.99."""
    return (Decimal(int(value)) / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


# ---------- Пошук за назвою ----------

# Лапки прибираємо, різні апострофи зводимо до одного: «Галичина» = Галичина, сир'ний = сирʼний.
_SEARCH_CHARS = str.maketrans(
    {"«": " ", "»": " ", '"': " ", "“": " ", "”": " ", "„": " ", "’": "'", "ʼ": "'", "`": "'"}
)
_TOKEN_EDGE = ".,;:!?()[]%®™"


def search_text(*parts: str | None) -> str:
    """Нормалізований текст для пошуку. Рахується в Python, тож не залежить від локалі БД (lower() для кирилиці)."""
    text = " ".join(p for p in parts if p).translate(_SEARCH_CHARS).lower()
    return re.sub(r"\s+", " ", text).strip()


def search_tokens(query: str | None) -> list[str]:
    """Слова запиту для пошуку: 'Молоко «Галичина» 2,5%' -> ['молоко', 'галичина', '2,5']."""
    tokens = (t.strip(_TOKEN_EDGE) for t in search_text(query).split())
    return [t for t in tokens if len(t) >= 2 or t.isdigit()]


# ---------- GTIN / EAN ----------


def norm_gtin(code: object) -> str | None:
    """'04820222760249' (Zakaz) і '4820222760249' (Сільпо) -> '4820222760249'. Нецифрові коди -> None."""
    digits = str(code or "").strip()
    if not digits.isdigit():
        return None
    digits = digits.lstrip("0")
    if not 8 <= len(digits) <= 14:
        return None
    return digits.zfill(13)


def is_internal_code(gtin: str) -> bool:
    """Префікс 2 (20–29) означає коди обмеженого обігу. Магазин друкує їх сам, тому між мережами вони не збігаються."""
    return gtin.zfill(13).startswith(("2", "02"))


def pick_gtins(codes: list[object]) -> tuple[str | None, list[str]]:
    """Головний GTIN (публічний, 13 цифр, якщо є) і решта кодів товару."""
    normed: list[str] = []
    for code in codes:
        gtin = norm_gtin(code)
        if gtin and gtin not in normed:
            normed.append(gtin)
    public = [g for g in normed if not is_internal_code(g)]
    primary = next((g for g in public if len(g) == 13), public[0] if public else None)
    return primary, [g for g in normed if g != primary]


# ---------- Вага пачки й ціна за одиницю ----------

_UNITS: dict[str, tuple[Decimal, str]] = {
    "кг": (Decimal(1000), "g"),
    "гр": (Decimal(1), "g"),
    "г": (Decimal(1), "g"),
    "л": (Decimal(1000), "ml"),
    "мл": (Decimal(1), "ml"),
}
_NOT_LETTER = r"(?![а-яіїєґa-z])"
_MULTI_RE = re.compile(r"(\d+)\s*[хxX×*]\s*(\d+(?:[.,]\d+)?)\s*(кг|гр|г|мл|л)" + _NOT_LETTER, re.IGNORECASE)
_SINGLE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(кг|гр|г|мл|л|шт)" + _NOT_LETTER, re.IGNORECASE)


def _num(text: str) -> Decimal:
    return Decimal(text.replace(",", "."))


def parse_pack(text: str | None) -> tuple[Decimal | None, str | None]:
    """Вага пачки з назви: '950г' -> (950, 'g'), '1,5 кг' -> (1500, 'g'), '0.9 л' -> (900, 'ml'),
    '2х200г' -> (400, 'g'), '10шт' -> (10, 'pcs')."""
    if not text:
        return None, None
    text = text.replace(" ", " ")
    multi = _MULTI_RE.search(text)
    if multi:
        factor, unit = _UNITS[multi.group(3).lower()]
        return int(multi.group(1)) * _num(multi.group(2)) * factor, unit
    single = _SINGLE_RE.search(text)
    if not single:
        return None, None
    unit_text = single.group(2).lower()
    if unit_text == "шт":
        return _num(single.group(1)), "pcs"
    factor, unit = _UNITS[unit_text]
    return _num(single.group(1)) * factor, unit


def unit_price(price: Decimal, pack_qty: Decimal | None, pack_unit: str | None) -> Decimal | None:
    """Ціна за кг / л (для g, ml) або за штуку (для pcs)."""
    if not pack_qty or pack_qty <= 0:
        return None
    per = price / pack_qty * (1 if pack_unit == "pcs" else 1000)
    return per.quantize(CENT, rounding=ROUND_HALF_UP)


_FAT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def parse_fat(title: str | None, fat_field: str | None = None) -> Decimal | None:
    for text in (fat_field, title):
        match = _FAT_RE.search(text or "")
        if match:
            value = _num(match.group(1))
            if 0 <= value <= 100:
                return value
    return None


# ---------- Теги складу ----------

DAIRY = frozenset({"milk", "kefir", "curd", "sour_cream", "butter", "cheese"})
COMPOSITION_TAGS = frozenset({"sugar", "palm_oil"})
PRIVATE_LABELS = frozenset({"auchan", "ашан", "novus", "metro chef", "aro", "повна чаша", "premiya", "розумний вибір"})

_NO_SUGAR_RE = re.compile(r"без\s+(?:додан\w*\s+|додавання\s+)?цукр\w*", re.IGNORECASE)
_SUGAR_RE = re.compile(r"цукор|цукру|сироп|глюкоз|фруктоз|декстроз", re.IGNORECASE)
_PALM_RE = re.compile(r"пальм|рослинн\w*\s+жир|замінник\w*\s+молочного\s+жиру|\bзмж\b", re.IGNORECASE)
_LACTOSE_FREE_RE = re.compile(r"без\s*лактоз|безлактоз", re.IGNORECASE)
_MILK_INGREDIENT_RE = re.compile(r"молок|вершк|сироватк|лактоз", re.IGNORECASE)


def composition_tags(ingredients: str | None) -> list[str]:
    """Теги за реальним складом. Порожній склад дає порожній список, але це означає «невідомо», а не «чисто».

    Не використовуй nutrition_facts.sugars для «без цукру»: у молоці 4.7 г природної лактози.
    """
    text = ingredients or ""
    tags = []
    if _SUGAR_RE.search(_NO_SUGAR_RE.sub(" ", text)):
        tags.append("sugar")
    if _PALM_RE.search(text):
        tags.append("palm_oil")
    return tags


def build_tags(category: str, title: str, brand: str | None, ingredients: str | None) -> list[str]:
    tags = set(composition_tags(ingredients))
    lactose_free = bool(_LACTOSE_FREE_RE.search(title) or _LACTOSE_FREE_RE.search(ingredients or ""))
    if not lactose_free and (category in DAIRY or _MILK_INGREDIENT_RE.search(ingredients or "")):
        tags.add("lactose")
    if brand and brand.strip().lower() in PRIVATE_LABELS:
        tags.add("private_label")
    return sorted(tags)
