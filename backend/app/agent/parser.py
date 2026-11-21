"""Крок Parse: текст → ParsedRequest. LLM, а якщо вона недоступна — простий парсер на правилах."""

import logging
import re

from app.agent.llm import llm_enabled, parse_with_llm
from app.agent.schemas import Constraints, ParsedRequest, RequestedItem

log = logging.getLogger(__name__)

# Запасний словник: основа слова → позиція. Рецептів не знає — для цього потрібна LLM.
_KEYWORDS: dict[str, RequestedItem] = {
    "молок": RequestedItem(name="молоко", search_query="молоко", category="milk", quantity=1000, unit="ml"),
    "кефір": RequestedItem(name="кефір", search_query="кефір", category="kefir", quantity=1000, unit="ml"),
    "кисломолоч": RequestedItem(
        name="сир кисломолочний", search_query="сир кисломолочний", category="curd", quantity=500, unit="g"
    ),
    "сметан": RequestedItem(name="сметана", search_query="сметана", category="sour_cream", quantity=300, unit="g"),
    "масл": RequestedItem(name="масло вершкове", search_query="масло", category="butter", quantity=200, unit="g"),
    "яйц": RequestedItem(name="яйця", search_query="яйця", category="eggs", quantity=10, unit="pcs"),
    "яєць": RequestedItem(name="яйця", search_query="яйця", category="eggs", quantity=10, unit="pcs"),
    "борошн": RequestedItem(name="борошно", search_query="борошно", category="flour", quantity=1000, unit="g"),
    "гречк": RequestedItem(name="гречка", search_query="гречка", category="buckwheat", quantity=1000, unit="g"),
    "рис": RequestedItem(name="рис", search_query="рис", category="rice", quantity=1000, unit="g"),
    "хліб": RequestedItem(name="хліб", search_query="хліб", category="bread", quantity=1, unit="pcs"),
    "кав": RequestedItem(name="кава", search_query="кава", category="coffee_ground", quantity=1, unit="pcs"),
    "чай": RequestedItem(name="чай", search_query="чай", category="tea", quantity=1, unit="pcs"),
    "банан": RequestedItem(name="банани", search_query="банани", category="bananas", quantity=1000, unit="g"),
    "яблук": RequestedItem(name="яблука", search_query="яблука", category="apples", quantity=1000, unit="g"),
}
_EXCLUDE = {"цукр": "sugar", "пальмов": "palm_oil", "лактоз": "lactose"}
_CHAINS = {
    "сільпо": "silpo", "novus": "novus", "новус": "novus", "ашан": "auchan", "auchan": "auchan",
    "metro": "metro", "метро": "metro", "ультрамаркет": "ultramarket", "еко маркет": "ekomarket",
    "мегамаркет": "megamarket", "таврі": "tavriav",
}  # fmt: skip


def parse_rules(text: str) -> ParsedRequest:
    t = text.lower()
    items: list[RequestedItem] = []
    for key, item in _KEYWORDS.items():
        if key in t and all(i.name != item.name for i in items):
            items.append(item.model_copy())

    c = Constraints()
    if m := re.search(r"(\d+)\s*(грн|гривень|гривні)", t):
        c.budget_uah = float(m.group(1))
    for chunk in re.findall(r"без\s+([^\s,.]+(?:\s+[^\s,.]+)?)", t):
        c.exclude += [tag for key, tag in _EXCLUDE.items() if key in chunk and tag not in c.exclude]
    if "авто" in t or "машин" in t:
        c.travel_mode = "car"
    if m := re.search(r"(\d+(?:[.,]\d+)?)\s*км", t):
        c.radius_km = float(m.group(1).replace(",", "."))
    elif "далеко не" in t or "поруч" in t:
        c.radius_km = 1.0
    c.preferred_chains = list(dict.fromkeys(v for k, v in _CHAINS.items() if k in t))
    return ParsedRequest(items=items, constraints=c)


async def parse_request(text: str) -> tuple[ParsedRequest, str]:
    """Повертає (розбір, "llm" | "rules"). Будь-яка помилка LLM (429, 503, таймаут) → парсер на правилах."""
    if llm_enabled():
        try:
            return await parse_with_llm(text), "llm"
        except Exception:
            log.exception("LLM parse failed, falling back to rules")
    return parse_rules(text), "rules"
