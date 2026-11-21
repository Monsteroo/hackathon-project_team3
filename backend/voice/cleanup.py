"""Чистка розшифровки + витяг режиму пересування і радіуса.

1. LLM (Groq `qwen/qwen3.8-27b`, запасна `openai/gpt-oss-120b`, temperature 0, JSON-режим):
   прибирає «ееее/ну/типу», числа → цифри з одиницями, повертає {text, mode, radius_km}.
2. Захист від галюцинацій: якщо в очищеному тексті є змістовне слово, якого не було в сирому
   (новий продукт/бренд/обмеження), — повертаємо сирий текст (`guard: "rejected"`).
3. Якщо LLM недоступна — правила (regex) для mode/radius, текст сирий.

Правила для режиму/радіуса (рішення команди 21.11):
  «пішки» → walk; «на машині/авто» → car; «недалеко/поруч/далеко не хочу» → walk, 1 км;
  явне «в радіусі 3 км / 500 метрів» → radius_km. Не згадано → null (фронт лишає поточний перемикач).
"""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher

import httpx

from backend.config import get_settings

log = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = 10.0
NEAR_RADIUS_KM = 1.0
MAX_RADIUS_KM = 50.0

SYSTEM_PROMPT = """Ти обробляєш розшифровку голосового запиту українською для застосунку покупок продуктів.
Поверни ЛИШЕ JSON: {"text": string, "mode": "walk" | "car" | null, "radius_km": number | null}.

text — очищений запит:
- прибери слова-паразити (ееее, ммм, ну, типу, короче, як би, значить) і повтори; при самовиправленні лиши останній варіант;
- числа пиши цифрами з одиницями: грн, г, кг, л, мл, шт («двісті п'ятдесят гривень» → «250 грн», «півтора кіло» → «1,5 кг», «два десятки яєць» → «20 яєць»);
- прибери з text фрази про відстань і транспорт (вони йдуть у mode/radius_km);
- НЕ додавай продуктів, брендів, кількостей чи обмежень, яких не було; НЕ перекладай і НЕ транслітеруй назви; не змінюй відмінки слів без потреби; не відповідай на запит.

mode: "walk" — якщо пішки або хочуть недалеко/поруч/близько; "car" — на машині/авто/автомобілем/доїду; інакше null.
radius_km: явний радіус у км («в радіусі 3 км» → 3, «до 500 метрів» → 0.5); якщо лише «недалеко/поруч/далеко не хочу» → 1; інакше null."""

UNITS = {"грн", "г", "гр", "кг", "л", "мл", "шт", "км", "м", "уп", "пач", "гривень", "гривні", "гривня",
         "кілограм", "кілограми", "кілограмів", "грам", "грамів", "літр", "літри", "літрів", "штук", "штуки"}
WORD_RE = re.compile(r"[\w'’ʼ]+", re.UNICODE)

_NUM_WORDS = {"пів": 0.5, "півтора": 1.5, "півтори": 1.5, "один": 1, "одного": 1, "одна": 1, "одну": 1,
              "два": 2, "дві": 2, "двох": 2, "три": 3, "трьох": 3, "чотири": 4, "чотирьох": 4,
              "п'ять": 5, "п'яти": 5, "шість": 6, "шести": 6, "сім": 7, "семи": 7, "вісім": 8,
              "десять": 10, "десяти": 10, "п'ятсот": 500, "триста": 300, "двісті": 200, "сто": 100}
_NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted(map(re.escape, _NUM_WORDS), key=len, reverse=True)) + r")"
RADIUS_RE = re.compile(_NUM + r"\s*(км|кілометр\w*|метр\w*|м)(?![\w])", re.IGNORECASE)
CAR_RE = re.compile(r"(на\s+машин\w*|машиною|на\s+авто\w*|автомобіл\w*|доїд\w*|поїд(у|емо)\b|їхати|на\s+таксі)",
                    re.IGNORECASE)
WALK_RE = re.compile(r"(пішки|пішочки|прогул\w*)", re.IGNORECASE)
NEAR_RE = re.compile(r"(недалеко|неподалік|поруч|поряд|близько|біля\s+дому|"
                     r"далеко\s+(йти\s+|іти\s+|ходити\s+)?не\s+хочу|не\s+хочу\s+(йти\s+|іти\s+|ходити\s+)?далеко)",
                     re.IGNORECASE)


def _norm_apostrophe(s: str) -> str:
    return s.replace("’", "'").replace("ʼ", "'")


def rule_constraints(text: str) -> dict:
    t = _norm_apostrophe(text.lower())
    radius = None
    if m := RADIUS_RE.search(t):
        raw_num, unit = m.group(1), m.group(2)
        num = _NUM_WORDS.get(raw_num) or float(raw_num.replace(",", "."))
        radius = num if unit.startswith(("км", "кіло")) else num / 1000
    mode = "car" if CAR_RE.search(t) else "walk" if WALK_RE.search(t) else None
    if NEAR_RE.search(t):
        mode = mode or "walk"
        radius = radius or NEAR_RADIUS_KM
    return {"mode": mode, "radius_km": _valid_radius(radius)}


def _valid_radius(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, 2) if 0.1 <= v <= MAX_RADIUS_KM else None


def _tokens(s: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(_norm_apostrophe(s))]


def new_content_words(raw: str, cleaned: str) -> list[str]:
    """Змістовні слова очищеного тексту, яких немає в сирому (з урахуванням відмінків)."""
    raw_tokens = _tokens(raw)
    out = []
    for w in _tokens(cleaned):
        if len(w) < 3 or any(c.isdigit() for c in w) or w in UNITS:
            continue
        if any(r[:3] == w[:3] or SequenceMatcher(None, r, w).ratio() >= 0.5 for r in raw_tokens):
            continue
        out.append(w)
    return out


def _llm(model: str, raw: str, client: httpx.Client) -> dict:
    s = get_settings()
    body = {"model": model, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": raw}]}
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    elif model.startswith("qwen/"):
        body["reasoning_format"] = "hidden"
    r = client.post(GROQ_CHAT_URL, json=body, headers={"Authorization": f"Bearer {s.groq_api_key}"})
    r.raise_for_status()
    j = r.json()
    data = json.loads(j["choices"][0]["message"]["content"])
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        raise ValueError("bad JSON shape")
    data["_usage"] = j.get("usage") or {}
    return data


def clean_text(raw: str, client: httpx.Client | None = None) -> dict:
    """→ {text, raw_text, mode, radius_km, cleanup: {model, guard, new_words}}"""
    raw = " ".join(raw.split())
    rules = rule_constraints(raw)
    result = {"text": raw, "raw_text": raw, **rules,
              "cleanup": {"model": None, "guard": "skipped", "new_words": [], "tokens": 0}}
    s = get_settings()
    if not raw or not s.groq_api_key:
        return result

    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        data, used = None, None
        for model in (s.groq_cleanup_model, s.groq_cleanup_fallback_model):
            if not model:
                continue
            try:
                data, used = _llm(model, raw, client), model
                break
            except Exception as e:  # noqa: BLE001
                log.warning("cleanup via %s failed: %s", model, e)
    finally:
        if own:
            client.close()
    if data is None:
        result["cleanup"]["guard"] = "llm_unavailable"
        return result

    cleaned = " ".join(data["text"].split())
    new_words = new_content_words(raw, cleaned)
    result["cleanup"] = {"model": used, "guard": "ok", "new_words": new_words,
                         "tokens": data["_usage"].get("total_tokens", 0)}
    if new_words or not cleaned:
        result["cleanup"]["guard"] = "rejected"   # LLM щось додала → не довіряємо, віддаємо сирий текст
    else:
        result["text"] = cleaned
        mode = data.get("mode") if data.get("mode") in ("walk", "car") else None
        radius = _valid_radius(data.get("radius_km"))
        # Правила точніші для явних чисел; LLM — для перефразувань. Беремо непорожнє.
        result["mode"] = mode or rules["mode"]
        result["radius_km"] = rules["radius_km"] if rules["radius_km"] is not None else radius
    return result
