"""Безпечний опис помилки для логів: лише тип і HTTP-статус.

Текст винятків httpx містить URL із параметрами — адресу, координати чи запит користувача,
тому в логи їх не пишемо.
"""
from __future__ import annotations


def err_summary(e: BaseException) -> str:
    status = getattr(getattr(e, "response", None), "status_code", None)
    return f"{type(e).__name__}{f' HTTP {status}' if status else ''}"


def parse_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "t", "yes"}
