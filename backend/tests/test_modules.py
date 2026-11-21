"""ENABLED_MODULES: можна підняти лише частину модулів (напр. окремий деплой каталогу)."""

import pytest

from app.config import get_settings
from app.main import create_app


def _prefixes(monkeypatch, value: str | None) -> set[str]:
    if value is None:
        monkeypatch.delenv("ENABLED_MODULES", raising=False)
    else:
        monkeypatch.setenv("ENABLED_MODULES", value)
    get_settings.cache_clear()
    paths = set(create_app().openapi()["paths"])  # те, що бачать клієнти й Swagger
    return {prefix for prefix in ("/catalog", "/geo", "/voice") if any(p.startswith(prefix + "/") for p in paths)}


def test_all_modules_by_default(monkeypatch):
    assert _prefixes(monkeypatch, None) == {"/catalog", "/geo", "/voice"}


def test_catalog_only_deploy(monkeypatch):
    assert _prefixes(monkeypatch, "catalog") == {"/catalog"}


def test_unknown_module_fails_fast(monkeypatch):
    monkeypatch.setenv("ENABLED_MODULES", "catalog,payments")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="payments"):
        create_app()
