"""Українські числівники → числа (для захисту чистки й витягу радіуса).

Потрібно, щоб перевірити: кожне число в очищеному тексті було сказане (цифрою чи словом),
і щоб розпізнати «в радіусі п'ятисот метрів», «не далі півтора кілометра».
"""

import re

_FORMS: dict[float, tuple[str, ...]] = {
    0.5: ("пів",),
    1: ("один", "одна", "одне", "одну", "одного", "одній", "одним"),
    1.5: ("півтора", "півтори"),
    2: ("два", "дві", "двох", "двом", "двома"),
    3: ("три", "трьох", "трьом", "трьома"),
    4: ("чотири", "чотирьох", "чотирьом"),
    5: ("п'ять", "п'яти", "п'ятьох"),
    6: ("шість", "шести", "шістьох"),
    7: ("сім", "семи", "сімох"),
    8: ("вісім", "восьми", "вісьмох"),
    9: ("дев'ять", "дев'яти"),
    10: ("десять", "десяти"),
    11: ("одинадцять", "одинадцяти"),
    12: ("дванадцять", "дванадцяти"),
    13: ("тринадцять", "тринадцяти"),
    14: ("чотирнадцять", "чотирнадцяти"),
    15: ("п'ятнадцять", "п'ятнадцяти"),
    16: ("шістнадцять", "шістнадцяти"),
    17: ("сімнадцять", "сімнадцяти"),
    18: ("вісімнадцять", "вісімнадцяти"),
    19: ("дев'ятнадцять", "дев'ятнадцяти"),
    20: ("двадцять", "двадцяти"),
    30: ("тридцять", "тридцяти"),
    40: ("сорок", "сорока"),
    50: ("п'ятдесят", "п'ятдесяти"),
    60: ("шістдесят", "шістдесяти"),
    70: ("сімдесят", "сімдесяти"),
    80: ("вісімдесят", "вісімдесяти"),
    90: ("дев'яносто",),
    100: ("сто", "ста"),
    200: ("двісті", "двохсот"),
    300: ("триста", "трьохсот"),
    400: ("чотириста", "чотирьохсот"),
    500: ("п'ятсот", "п'ятисот"),
    600: ("шістсот", "шестисот"),
    700: ("сімсот", "семисот"),
    800: ("вісімсот", "восьмисот"),
    900: ("дев'ятсот", "дев'ятисот"),
    1000: ("тисяча", "тисячі", "тисяч"),
}
NUM_WORDS: dict[str, float] = {f: v for v, forms in _FORMS.items() for f in forms}
DOZEN = {"десяток", "десятка", "десятки", "десятків"}
# Слова-одиниці, після яких LLM законно пише «1»: «молоко літр» → «1 л», «кілограм гречки» → «1 кг»
IMPLIED_ONE = ("літр", "кілограм", "кіло", "грам", "пачк", "штук", "пляшк", "банк", "упаковк", "кілометр", "метр")

DIGITS_RE = re.compile(r"\d+(?:[.,]\d+)?")
TOKEN_RE = re.compile(r"[\w']+")
NUMBER_WORD_ALT = "|".join(sorted(map(re.escape, NUM_WORDS), key=len, reverse=True))


def norm(s: str) -> str:
    return s.lower().replace("’", "'").replace("ʼ", "'")


def to_float(s: str) -> float:
    return float(s.replace(",", "."))


def spoken_values(text: str) -> set[float]:
    """Усі числа, які можна вивести з тексту: цифри, слова, складені («двісті п'ятдесят»), «два десятки»."""
    t = norm(text)
    values = {to_float(m) for m in DIGITS_RE.findall(t)}
    run: list[float] = []

    def flush():
        if run:
            values.update(run)
            values.add(sum(run))
            run.clear()

    for tok in TOKEN_RE.findall(t):
        if tok in NUM_WORDS:
            run.append(NUM_WORDS[tok])
        elif tok in DOZEN:
            n = sum(run) if run else 1
            run.clear()
            values.update({n, n * 10})
        elif DIGITS_RE.fullmatch(tok):
            flush()
        else:
            flush()
    flush()
    if any(u in t for u in IMPLIED_ONE):
        values.add(1.0)
    return values


def parse_number(s: str) -> float | None:
    """«3», «2,5», «трьох», «півтора», «двісті п'ятдесят» → число."""
    s = norm(s).strip()
    if DIGITS_RE.fullmatch(s):
        return to_float(s)
    parts = s.split()
    if parts and all(p in NUM_WORDS for p in parts):
        return sum(NUM_WORDS[p] for p in parts)
    return None


# --- Нормалізація чисел у сирому тексті (коли чистку LLM відкинуто або вона недоступна) -------------

_UNIT_ABBR = (
    (("гривень", "гривні", "гривня", "гривню", "гривен", "гривнях", "грн"), "грн"),
    (("кілограм", "кілограма", "кілограми", "кілограмів", "кіло", "кг"), "кг"),
    (("грам", "грама", "грами", "грамів", "г"), "г"),
    (("літр", "літра", "літри", "літрів", "л"), "л"),
    (("мілілітр", "мілілітра", "мілілітри", "мілілітрів", "мл"), "мл"),
    (("штука", "штуки", "штук", "шт"), "шт"),
    (("відсоток", "відсотки", "відсотків", "відсотка"), "%"),
)
UNIT_OF = {form: abbr for forms, abbr in _UNIT_ABBR for form in forms}
_UNIT_ALT = "|".join(sorted(UNIT_OF))
_DOZEN_ALT = "|".join(sorted(DOZEN))
_WRITTEN_NUMBER_ALT = NUMBER_WORD_ALT.replace("'", "['’ʼ]")
_QUANTITY_RE = re.compile(
    rf"(?<![\w'’ʼ])(?:"
    rf"(?P<number>{DIGITS_RE.pattern}|(?:{_WRITTEN_NUMBER_ALT})(?:\s+(?:{_WRITTEN_NUMBER_ALT}))*)"
    rf"(?:\s+(?P<dozen>{_DOZEN_ALT}))?(?:\s+(?P<unit>{_UNIT_ALT}))?"
    rf"|(?P<bare_dozen>десяток|десятка)|(?P<bare_unit>кілограм|кіло|літр)"
    rf")(?![\w'’ʼ])",
    re.IGNORECASE,
)


def _spoken_quantity(number: str) -> float | None:
    """Read a cardinal phrase, preserving adjacent quantities such as «два три»."""
    values = [NUM_WORDS[word] for word in number.split()]
    if len(values) == 1:
        return values[0]
    if any(not float(value).is_integer() for value in values) or values.count(1000) > 1:
        return None
    if 1000 in values:
        split = values.index(1000)
        groups = (values[:split], values[split + 1 :])
    else:
        groups = (values,)
    for group in groups:
        # A hundred can be followed by tens or units. A teen already includes the units.
        ranks = [100 if v >= 100 else 10 if v >= 10 else 1 for v in group]
        if ranks != sorted(set(ranks), reverse=True) or any(10 < v < 20 for v in group[:-1]):
            return None
    if len(groups) == 2:
        return (sum(groups[0]) or 1) * 1000 + sum(groups[1])
    return sum(values)


def normalize_numbers(text: str) -> str:
    """«Кілограм гречки, півтора кіло філе і десяток яєць, до трьохсот гривень» →
    «1 кг гречки, 1,5 кг філе і 10 яєць, до 300 грн». Решта тексту зберігається."""

    def replace(match: re.Match[str]) -> str:
        if match["bare_dozen"]:
            return "10"
        if match["bare_unit"]:
            return f"1 {UNIT_OF[norm(match['bare_unit'])]}"
        number = norm(match["number"])
        unit = UNIT_OF[norm(match["unit"])] if match["unit"] else ""
        if not unit and not match["dozen"] and number in {"ста", "пів"}:
            return match[0]
        if DIGITS_RE.fullmatch(number) and not match["dozen"]:
            value = number
        else:
            quantity = to_float(number) if DIGITS_RE.fullmatch(number) else _spoken_quantity(number)
            if quantity is None:
                return match[0]
            if match["dozen"]:
                quantity *= 10
            value = str(int(quantity)) if float(quantity).is_integer() else str(quantity).replace(".", ",")
        return f"{value} {unit}" if unit and unit != "%" else value + unit

    # Recognize curly apostrophes in numerals without altering them elsewhere in the transcript.
    return _QUANTITY_RE.sub(replace, text)
