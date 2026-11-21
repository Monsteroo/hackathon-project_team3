"""Чистка розшифровки + витяг режиму пересування і радіуса.

1. LLM (Groq `qwen/qwen3.8-27b`, запасна `openai/gpt-oss-120b`, temperature 0, JSON-режим):
   прибирає «ееее/ну/типу», числа → цифри з одиницями, повертає {text, mode, radius_km}.
2. Захист від галюцинацій (`guard_issues`): очищений текст відхиляється і повертається сирий
   із нормалізованими числами та валідними mode/radius від LLM
   (`guard: "rejected"`), якщо LLM
     * додала змістовне слово, якого не було (новий продукт/бренд: «+ масло», «+ сирок»);
     * написала число, якого не казали ні цифрою, ні словом («два кіло» → «5 кг»);
     * загубила «без / не / тільки / лише / крім» («молоко без лактози» → «молоко»);
     * викинула змістовне слово сирого тексту (крім слів-паразитів, фраз про транспорт/відстань
       і продуктів, скасованих самовиправленням «ой ні / точніше»).
3. Якщо LLM недоступна — правила для чисел і mode/radius.

Правила для режиму/радіуса (рішення команди 21.11):
  «пішки» → walk; «на машині/авто» → car (крім «не хочу їхати на машині»);
  «недалеко/поруч/далеко не хочу/близько до дому» → walk, 1 км (просто «близько 2 кг» — не відстань);
  радіус — лише в контексті «в радіусі / в межах / до / не далі / не більше» + число + км/м.
  Валідний радіус від LLM має пріоритет над правилами. Не згадано → null.
"""

import json
import logging
import re
from difflib import SequenceMatcher
from functools import lru_cache

import httpx

from app.config import get_settings
from app.geo.service import MAX_RADIUS_KM
from app.voice import vocabulary
from app.voice.errors import err_summary
from app.voice.numbers import (
    DIGITS_RE,
    DOZEN,
    NUM_WORDS,
    NUMBER_WORD_ALT,
    UNIT_OF,
    norm,
    normalize_numbers,
    parse_number,
    spoken_values,
    to_float,
)

log = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = 10.0
NEAR_RADIUS_KM = 1.0

SYSTEM_PROMPT = """Ти обробляєш розшифровку голосового запиту українською для застосунку покупок продуктів.
Поверни ЛИШЕ JSON: {"text": string, "mode": "walk" | "car" | null, "radius_km": number | null}.

text — очищений запит:
- прибери слова-паразити (ееее, ммм, ну, типу, короче, як би, значить) і повтори; при самовиправленні лиши останній варіант;
- числа пиши цифрами з одиницями: грн, г, кг, л, мл, шт («двісті п'ятдесят гривень» → «250 грн», «півтора кіло» → «1,5 кг», «два десятки яєць» → «20 яєць»);
- прибери з text фрази про відстань і транспорт (вони йдуть у mode/radius_km);
- зберігай «без», «не», «тільки», «лише», «крім» разом зі словами після них;
- явно спотворену розпізнаванням назву виправляй лише на схожу назву продукту чи бренду («ярчиця» → «гірчиця»);
- НЕ додавай продуктів, брендів, кількостей чи обмежень, яких не було; НЕ перекладай і НЕ транслітеруй назви; не змінюй відмінки слів без потреби; не відповідай на запит.

mode: "car" — якщо на машині/авто/автомобілем/доїду (але не «не хочу на машині»); "walk" — якщо пішки або хочуть недалеко/поруч; інакше null.
radius_km: явна межа в км («до 500 метрів» → 0.5, «не більше, щоб було одного кілометра» → 1) має пріоритет. Якщо межі немає, «недалеко/поруч/далеко не хочу/десь в районі, щоб був магазин» → 1; інакше null."""  # noqa: E501

UNITS = {
    "грн",
    "г",
    "гр",
    "кг",
    "л",
    "мл",
    "шт",
    "км",
    "м",
    "уп",
    "пач",
    "гривень",
    "гривні",
    "гривня",
    "кілограм",
    "кілограми",
    "кілограмів",
    "грам",
    "грамів",
    "літр",
    "літри",
    "літрів",
    "штук",
    "штуки",
    "кіло",
    "відсотків",
    "відсотки",
    "відсоток",
}
FILLERS = {
    "ееее",
    "еее",
    "ее",
    "е",
    "ммм",
    "мм",
    "ну",
    "типу",
    "короче",
    "як",
    "би",
    "значить",
    "так",
    "ой",
    "ні",
    "от",
    "ось",
    "це",
    "мені",
    "треба",
    "хочу",
    "хочеться",
    "купи",
    "купити",
    "купіть",
    "візьми",
    "взяти",
    "зробити",
    "потрібно",
    "потрібен",
    "потрібна",
    "будь",
    "ласка",
    "десь",
    "приблизно",
    "ще",
    "також",
    "і",
    "й",
    "та",
    "а",
    "для",
    "на",
    "по",
    "з",
    "із",
    "зі",
    "в",
    "у",
    "до",
    "від",
    "що",
    "щоб",
    "все",
    "всі",
}
KEEP_WORDS = ("без", "не", "тільки", "лише", "крім", "окрім")
CORRECTION_RE = re.compile(r"(ой,?\s*ні|а\s+ні|ні,|точніше|вірніше|тобто|краще)", re.IGNORECASE)
WORD_RE = re.compile(r"[\w']+", re.UNICODE)

_UNIT = r"(км|кілометр\w*|метр\w*|м)(?![\w'])"
_NUM = r"(\d+(?:[.,]\d+)?|(?:(?:" + NUMBER_WORD_ALT + r")\s+)?(?:" + NUMBER_WORD_ALT + r"))"
RADIUS_RE = re.compile(
    r"\b(?:радіус\w*|меж(?:ах|і)|(?:не\s+(?:було\s+)?)?далі|більше|до|максимум|"
    r"не\s+більше(?:[\s,]+(?:щоб|було|була|це|там|десь|приблизно|відстань|складала|до|як))*)"
    r"[\s,]+(?:за\s+)?" + _NUM + r"\s*" + _UNIT,
    re.IGNORECASE,
)
CAR_RE = re.compile(
    r"(на\s+машин\w*|машиною|на\s+авто\w*|автомобіл\w*|доїд\w*|поїд(?:у|емо)\b|їхати|на\s+таксі)", re.IGNORECASE
)
NEGATION_RE = re.compile(r"\bне\b[^,.;!?]{0,25}$", re.IGNORECASE)
WALK_RE = re.compile(r"(пішки|пішочки|піду|прогул\w*)", re.IGNORECASE)
NEAR_RE = re.compile(
    r"\b(?:щоб\s+(?:було\s+)?)?(?:(?:недалеко|неподалік|поруч|поряд)"
    r"(?:\s+(?:з|із|від)\s+(?:(?:моїм|мого|моєї)\s+)?(?:дом\w*|робот\w*|мною))?"
    r"(?:\s+(?:йти|іти|ходити|піти))?|біля\s+(?:дому|роботи)|близько\s+(?:до|від)\s+(?:дому|роботи|мене)|"
    r"далеко\s+(?:йти\s+|іти\s+|ходити\s+)?не\s+хочу|не\s+хочу\s+(?:йти\s+|іти\s+|ходити\s+)?далеко|"
    r"(?:десь\s+)?[ву]\s+районі[\s,]+щоб\s+був\s+магазин)\b",
    re.IGNORECASE,
)


def _mode_from_rules(t: str) -> str | None:
    """Останнє незаперечене згадування перемагає: «не хочу їхати на машині, піду пішки» → walk."""
    hits = []
    for m in CAR_RE.finditer(t):
        if not NEGATION_RE.search(t[: m.start()]):
            hits.append((m.start(), "car"))
    hits += [(m.start(), "walk") for m in WALK_RE.finditer(t)]
    return max(hits)[1] if hits else None


def rule_constraints(text: str) -> dict:
    t = norm(text)
    radius = None
    if m := RADIUS_RE.search(t):
        num, unit = parse_number(m.group(1)), m.group(2)
        if num is not None:
            radius = num if unit.startswith(("км", "кіло")) else num / 1000
    mode = _mode_from_rules(t)
    if NEAR_RE.search(t):
        mode = mode or "walk"
        radius = radius or NEAR_RADIUS_KM
    return {"mode": mode, "radius_km": _valid_radius(radius)}


DISTANCE_CUE_RE = re.compile(_NUM + r"\s*" + _UNIT, re.IGNORECASE)


def has_distance_cue(text: str) -> bool:
    """Чи людина взагалі сказала щось про відстань: явну межу («2 км», «до 500 метрів») або «недалеко/поруч».

    Без цього радіус від LLM не беремо: на просте «пішки» модель вигадує 1 км, і пошук стає вужчим
    за типовий пішохідний радіус (`DEFAULT_RADIUS_KM["walk"]` у модулі geo).
    """
    t = norm(text)
    return bool(RADIUS_RE.search(t) or NEAR_RE.search(t) or DISTANCE_CUE_RE.search(t))


def _valid_radius(v) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if 0.1 <= v <= MAX_RADIUS_KM else None


def _tokens(s: str) -> list[str]:
    return WORD_RE.findall(norm(s))


_ENDINGS = sorted(
    "ями ами ові еві ого ому ими іми ою ею их іх ах ях ам ям ів їв ей ий ій ої а я о е є и і ї у ю ь".split(),
    key=len,
    reverse=True,
)
# Чергування залежить від лексеми. Глобальна заміна голосних ототожнює різні слова.
_EGG_FORMS = frozenset("яйце яйця яйцю яйцем яйці яєць яйцям яйцями яйцях".split())


def _stem(word: str) -> str:
    if word in _EGG_FORMS:
        return "яйц"
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


UNIT_STEMS = ("літр", "грам", "гривн", "метр", "кілометр", "пачк")


def _is_number_or_unit(w: str) -> bool:
    return w in UNITS or w in UNIT_OF or w in NUM_WORDS or w in DOZEN or w.startswith(UNIT_STEMS) or w.isdecimal()


VOCAB_FIX_RATIO = 0.65


@lru_cache
def _vocabulary_stems() -> frozenset[str]:
    return frozenset(_stem(word) for word in vocabulary.words())


def _unmatched_words(
    raw: list[str], cleaned: list[str], core: list[str], corrected: set[str]
) -> tuple[list[str], list[str]]:
    raw_stems = {_stem(word) for word in raw}
    clean_stems = {_stem(word) for word in cleaned}
    added = [
        w
        for w in cleaned
        if len(w) >= 3 and not w.isdecimal() and w not in UNITS and w not in UNIT_OF and _stem(w) not in raw_stems
    ]
    lost = [
        w
        for w in core
        if w not in FILLERS
        and w not in KEEP_WORDS
        and w not in corrected
        and not _is_number_or_unit(w)
        and _stem(w) not in clean_stems
    ]
    vocab = _vocabulary_stems()
    # A correction consumes one missing, unrecognised word. Known products cannot be replaced.
    unknown = {w for w in lost if _stem(w) not in vocab and len(w) >= 4 and w.isalpha()}
    fixes = sorted(
        (SequenceMatcher(None, source, target).ratio(), source, target)
        for target in set(added)
        if _stem(target) in vocab
        for source in unknown
    )
    fixed_sources, fixed_targets = set(), set()
    for score, source, target in reversed(fixes):
        if score >= VOCAB_FIX_RATIO and source not in fixed_sources and target not in fixed_targets:
            fixed_sources.add(source)
            fixed_targets.add(target)
    return [w for w in added if w not in fixed_targets], [w for w in lost if w not in fixed_sources]


def new_content_words(raw: str, cleaned: str) -> list[str]:
    """Змістовні слова очищеного тексту, яких немає в сирому."""
    tokens = _tokens(raw)
    return _unmatched_words(tokens, _tokens(cleaned), tokens, set())[0]


def _strip_transport_phrases(t: str) -> str:
    """Фрази про відстань/транспорт LLM прибирає з text за інструкцією — їх не перевіряємо."""
    for rx in (RADIUS_RE, NEAR_RE, CAR_RE, WALK_RE):
        t = rx.sub(" ", t)
    return re.sub(r"\b(не\s+хочу|не\s+буду|не\s+треба)\b(?=[\s,.;]*(?:$|[,.;]))", " ", t)


def guard_issues(raw: str, cleaned: str) -> dict[str, list]:
    """Порожній словник = очищений текст безпечний."""
    issues: dict[str, list] = {}
    spoken = spoken_values(raw)
    extra_nums = [n for n in DIGITS_RE.findall(norm(cleaned)) if not any(abs(to_float(n) - v) < 1e-6 for v in spoken)]
    if extra_nums:
        issues["new_numbers"] = extra_nums

    raw_core = _strip_transport_phrases(norm(raw))
    raw_t, clean_t = _tokens(raw_core), _tokens(cleaned)
    lost_keep = [k for k in KEEP_WORDS if raw_t.count(k) > clean_t.count(k)]
    if lost_keep:
        issues["lost_restrictions"] = lost_keep

    # слова перед «ой ні / точніше» можна законно прибрати (самовиправлення)
    corrected: set[str] = set()
    for m in CORRECTION_RE.finditer(raw_core):
        corrected.update(_tokens(raw_core[: m.start()])[-3:])
    added, lost = _unmatched_words(_tokens(raw), clean_t, raw_t, corrected)
    if added:
        issues["new_words"] = added
    if lost:
        issues["lost_words"] = lost
    return issues


async def _llm(model: str, raw: str, client: httpx.AsyncClient) -> dict:
    s = get_settings()
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": raw}],
    }
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    elif model.startswith("qwen/"):
        body["reasoning_format"] = "hidden"
    r = await client.post(GROQ_CHAT_URL, json=body, headers={"Authorization": f"Bearer {s.groq_api_key}"})
    r.raise_for_status()
    j = r.json()
    data = json.loads(j["choices"][0]["message"]["content"])
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        raise ValueError("bad JSON shape")
    data["_usage"] = j.get("usage") or {}
    return data


async def clean_text(raw: str, client: httpx.AsyncClient | None = None) -> dict:
    """→ {text, raw_text, mode, radius_km, cleanup: {model, guard, new_words, issues, tokens}}"""
    raw = " ".join(raw.split())
    rules = rule_constraints(raw)
    result = {
        "text": normalize_numbers(raw),
        "raw_text": raw,
        **rules,
        "cleanup": {"model": None, "guard": "skipped", "new_words": [], "issues": {}, "tokens": 0},
    }
    s = get_settings()
    if not raw or not s.groq_api_key:
        return result

    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        data, used = None, None
        for model in (s.groq_cleanup_model, s.groq_cleanup_fallback_model):
            if not model:
                continue
            try:
                data, used = await _llm(model, raw, client), model
                break
            except Exception as e:  # noqa: BLE001
                log.warning("cleanup via %s failed: %s", model, err_summary(e))
    finally:
        if own:
            await client.aclose()
    if data is None:
        result["cleanup"]["guard"] = "llm_unavailable"
        return result

    cleaned = " ".join(data["text"].split())
    issues = guard_issues(raw, cleaned) if cleaned else {"empty": [True]}
    result["cleanup"] = {
        "model": used,
        "guard": "rejected" if issues else "ok",
        "new_words": issues.get("new_words", []),
        "issues": issues,
        "tokens": data["_usage"].get("total_tokens", 0),
    }
    mode = data.get("mode") if data.get("mode") in ("walk", "car") else None
    radius = _valid_radius(data.get("radius_km")) if has_distance_cue(raw) else None
    result["mode"] = mode or rules["mode"]
    result["radius_km"] = radius if radius is not None else rules["radius_km"]
    if not issues:
        result["text"] = cleaned
    return result
