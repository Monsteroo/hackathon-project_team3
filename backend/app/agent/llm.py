# ruff: noqa: E501 — системний промпт: довгі рядки тексту для моделі, переносити їх немає сенсу
"""LLM-розбір запиту: Claude (Anthropic SDK) або Gemini / Groq / Grok (OpenAI-сумісний API).

Провайдер обирається через LLM_PROVIDER; промпт і схема спільні.
"""

from functools import lru_cache

import anthropic
from openai import AsyncOpenAI

from app.agent.schemas import ParsedRequest
from app.config import get_settings

SYSTEM_PROMPT = """Ти розбираєш голосовий запит покупця українського супермаркету на структурований список покупок.

Правила:
- Страву чи рецепт розклади на інгредієнти з кількістю на вказану кількість порцій (за замовчуванням 2). Не додавай те, що зазвичай уже є вдома (сіль, вода), якщо про це не просили.
- Одиниці лише g, ml або pcs: «літр» = 1000 ml, «кілограм» = 1000 g, «десяток яєць» = 10 pcs, «пачка кави» = 1 pcs.
- name — коротка назва українською. search_query — 1–3 слова, якими товар названо в каталозі супермаркету (штучні товари в множині: «яйця курячі», «банани»), без вигаданих брендів і без прикметників-обмежень.
- category — одна з канонічних категорій каталогу, якщо товар до неї належить: milk (молоко), kefir, curd (кисломолочний сир), sour_cream, butter, cheese (твердий сир), eggs, flour, sugar, vanilla_sugar (ванільний цукор, ванілін), buckwheat, rice, pasta, sunflower_oil, bread, coffee_ground (мелена кава; «кава» без уточнень теж сюди), coffee_beans, tea, bananas, apples. Для інших товарів — null.
- brand заповнюй лише тоді, коли користувач сам назвав бренд.
- «без цукру» → constraints.exclude = ["sugar"]; «без пальмової олії» → "palm_oil"; «без лактози» → "lactose". Виключений інгредієнт ніколи не додавай в items, навіть якщо він є в класичному рецепті.
- Бюджет «до 400 грн», «маю 400 гривень» → constraints.budget_uah = 400.
- «далеко не хочу», «поруч» → radius_km = 1. «в радіусі N км» → radius_km = N. «на авто», «на машині» → travel_mode = "car", інакше "walk".
- Згадані мережі → preferred_chains: Сільпо = silpo, Novus = novus, Ашан = auchan, Metro = metro, Ультрамаркет = ultramarket, ЕКО маркет = ekomarket, Мегамаркет = megamarket, Таврія В = tavriav. Інших мереж у каталозі немає — не вигадуй.
- Необов'язкові інгредієнти (ванілін, прянощі, зелень для прикраси) познач optional = true.
- servings — кількість порцій, якщо її названо.
- Якщо в запиті немає жодного продукту, поверни порожній items."""

# Токени останнього виклику — для евалів і підрахунку вартості
LAST_USAGE: dict[str, int] = {}


def llm_enabled() -> bool:
    s = get_settings()
    if s.llm_provider == "anthropic":
        return bool(s.anthropic_api_key)
    return bool(s.llm_api_key and s.llm_model)


async def parse_with_llm(text: str) -> ParsedRequest:
    if get_settings().llm_provider == "anthropic":
        parsed = await _parse_claude(text)
    else:
        parsed = await _parse_openai_compat(text)

    # Страховка: модель іноді додає виключений інгредієнт (цукор у сирники) як позицію
    banned = set(parsed.constraints.exclude)
    if "sugar" in banned:
        banned.add("vanilla_sugar")
    parsed.items = [i for i in parsed.items if i.category not in banned]
    return parsed


# ---------- Claude ----------
@lru_cache
def _claude_client(api_key: str, timeout: float) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=1)


async def _parse_claude(text: str) -> ParsedRequest:
    s = get_settings()
    response = await _claude_client(s.anthropic_api_key, s.llm_timeout_s).messages.parse(
        model=s.anthropic_model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_format=ParsedRequest,
        output_config={"effort": s.anthropic_effort},
    )
    LAST_USAGE.update(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
    if response.stop_reason == "refusal":
        raise ValueError(f"claude refused: {response.stop_details}")
    if response.parsed_output is None:
        raise ValueError(f"claude returned no structured output (stop_reason={response.stop_reason})")
    return response.parsed_output


# ---------- Gemini / Groq / Grok ----------
@lru_cache
def _openai_client(api_key: str, base_url: str, timeout: float) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1)


async def _parse_openai_compat(text: str) -> ParsedRequest:
    s = get_settings()
    completion = await _openai_client(s.llm_api_key, s.llm_base_url, s.llm_timeout_s).chat.completions.parse(
        model=s.llm_model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        response_format=ParsedRequest,
        reasoning_effort=s.llm_reasoning_effort,
    )
    if completion.usage:
        LAST_USAGE.update(input_tokens=completion.usage.prompt_tokens, output_tokens=completion.usage.completion_tokens)
    message = completion.choices[0].message
    if message.parsed is None:
        raise ValueError(f"llm returned no structured output: {message.refusal or message.content!r}")
    return message.parsed
