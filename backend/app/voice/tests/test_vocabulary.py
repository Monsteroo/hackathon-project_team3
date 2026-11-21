from app.voice import vocabulary


def test_vocabulary_has_categories_problem_words_and_brands():
    p = set(vocabulary.phrases())
    assert {"гірчиця", "морозиво", "печиво", "борошно", "апельсини", "Моршинська"} <= p  # спотворені на живому голосі
    assert {"молоко", "кефір", "яйця", "гречка", "банани", "яблука"} <= p  # канонічні категорії каталогу
    assert {"Галичина", "Торчин", "Рошен"} <= p


def test_whisper_prompt_fits_budget_and_keeps_priority():
    prompt = vocabulary.whisper_prompt()
    assert prompt.startswith("Список покупок: гірчиця, морозиво")
    assert len(prompt) <= vocabulary.PROMPT_MAX_CHARS
    assert vocabulary.whisper_prompt(40) == "Список покупок: гірчиця, морозиво"  # обрізаємо хвіст, не середину


def test_words_are_lowercase_tokens():
    w = vocabulary.words()
    assert {"гірчиця", "моршинська", "кола", "зеро"} <= w
    assert all(x == x.lower() and len(x) >= 3 for x in w)
