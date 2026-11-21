"""Валідація ендпоінтів каталогу. Ці перевірки спрацьовують до звернення до БД, тож БД не потрібна."""

from httpx import ASGITransport, AsyncClient

from app.catalog.etl.normalize import search_text, search_tokens
from app.main import app


async def _get(path: str, params=None):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "test-api-key"}
    ) as client:
        return await client.get(path, params=params)


async def test_prices_requires_a_query():
    assert (await _get("/catalog/prices")).status_code == 422
    assert (await _get("/catalog/prices", {"q": "a"})).status_code == 422


async def test_prices_rejects_query_without_words():
    response = await _get("/catalog/prices", {"q": "%%"})
    assert response.status_code == 422
    assert response.json()["detail"] == "query has no searchable words"


async def test_prices_limits_store_ids():
    response = await _get("/catalog/prices", {"q": "молоко", "store_ids": ",".join(str(i) for i in range(301))})
    assert response.status_code == 422


def test_search_text_is_locale_independent_lowercase():
    assert search_text("Молоко «Галичина» 2,5%", "Галичина") == "молоко галичина 2,5% галичина"
    assert search_tokens("Молоко «Галичина» 2,5%") == ["молоко", "галичина", "2,5"]
    assert search_tokens("сир’ний") == search_tokens("сирʼний")
