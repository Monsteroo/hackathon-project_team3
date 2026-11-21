"""Спільні фікстури тестів бекенду."""

import pytest

from app.config import get_settings

TEST_API_KEYS = ("test-api-key", "second-test-key")


@pytest.fixture(autouse=True)
def _api_keys(monkeypatch):
    """Тестові ключі замість тих, що в backend/.env, щоб тести не залежали від локальних налаштувань."""
    monkeypatch.setenv("API_KEYS", ",".join(TEST_API_KEYS))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
