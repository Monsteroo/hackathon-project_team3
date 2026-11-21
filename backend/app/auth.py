"""Авторизація API за ключем у заголовку X-API-Key.

Підключається на рівні роутера модуля (див. app/main.py), тож новий модуль захищений одним рядком.
Модулі, які викликають сервіси каталогу напряму в Python (наприклад, агент), ключ не передають.
"""

import secrets
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

API_KEY_HEADER = "X-API-Key"

_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="Ключ доступу до API. Видає власник бекенду, на сервері задається в API_KEYS.",
)


async def require_api_key(api_key: Annotated[str | None, Security(_api_key_header)] = None) -> None:
    keys = get_settings().api_key_list
    if not keys:
        # Fail closed: помилка конфігурації не повинна тихо відкривати API всім.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API keys are not configured on the server (set API_KEYS)",
        )
    # compare_digest — порівняння за сталий час, щоб час відповіді не підказував, наскільки ключ близький.
    if not api_key or not any(secrets.compare_digest(api_key.encode(), key.encode()) for key in keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
