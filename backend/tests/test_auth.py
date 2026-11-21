"""Авторизація за X-API-Key. Ці перевірки спрацьовують до звернення до БД, тож БД не потрібна."""

from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app

KEY = "test-api-key"  # див. conftest.py
PROTECTED = "/catalog/prices?q=a"  # з правильним ключем дає 422 (валідація q), тобто до БД не доходить


async def _get(path: str, headers: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_health_stays_open():
    assert (await _get("/health")).status_code == 200


async def test_missing_key_is_rejected_before_validation():
    response = await _get(PROTECTED)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"


async def test_wrong_key_is_rejected():
    assert (await _get(PROTECTED, {"X-API-Key": "nope"})).status_code == 401
    assert (await _get("/health/db", {"X-API-Key": "nope"})).status_code == 401


async def test_any_configured_key_is_accepted():
    assert (await _get(PROTECTED, {"X-API-Key": KEY})).status_code == 422
    assert (await _get(PROTECTED, {"X-API-Key": "second-test-key"})).status_code == 422


async def test_without_configured_keys_api_is_closed(monkeypatch):
    monkeypatch.setenv("API_KEYS", "")
    get_settings.cache_clear()
    response = await _get(PROTECTED, {"X-API-Key": KEY})
    assert response.status_code == 503


async def test_openapi_declares_the_key_for_swagger():
    schema = (await _get("/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Ключ доступу до API. Видає власник бекенду, на сервері задається в API_KEYS.",
    }
    assert schema["paths"]["/catalog/prices"]["get"]["security"] == [{"APIKeyHeader": []}]
    assert "security" not in schema["paths"]["/health"]["get"]
