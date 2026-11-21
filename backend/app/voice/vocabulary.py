"""Словник продуктів і брендів (app/voice/data/vocabulary.txt) для підказки Whisper і захисту чистки."""

import re
from functools import lru_cache
from pathlib import Path

VOCAB_FILE = Path(__file__).resolve().parent / "data" / "vocabulary.txt"

# Whisper враховує лише останні ~224 токени підказки. Для кирилиці його токенізатор дає приблизно
# 1 токен на 2 символи, тому тримаємо підказку в межах ~420 символів (з запасом) — ОЦІНКА, не точний підрахунок.
PROMPT_MAX_CHARS = 420
PROMPT_PREFIX = "Список покупок: "


@lru_cache
def phrases() -> tuple[str, ...]:
    """Назви у порядку пріоритету (як у файлі), без коментарів і дублів."""
    if not VOCAB_FILE.exists():
        return ()
    seen: dict[str, None] = {}
    for line in VOCAB_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seen.setdefault(line, None)
    return tuple(seen)


@lru_cache
def words() -> frozenset[str]:
    """Окремі слова словника в нижньому регістрі (для виправлення назв у захисті)."""
    return frozenset(w for p in phrases() for w in re.findall(r"[\w']+", p.lower().replace("’", "'")) if len(w) >= 3)


@lru_cache
def whisper_prompt(max_chars: int = PROMPT_MAX_CHARS) -> str:
    """«Список покупок: гірчиця, морозиво, …» — стільки назв з початку файлу, скільки влазить у ліміт."""
    if not phrases():
        return ""
    out = PROMPT_PREFIX
    for i, p in enumerate(phrases()):
        piece = p if i == 0 else f", {p}"
        if len(out) + len(piece) > max_chars:
            break
        out += piece
    return out
